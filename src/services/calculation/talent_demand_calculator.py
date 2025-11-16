import logging
import numpy as np
from typing import Optional, List, Dict

from data.data_manager import DataManager
from data.game_state import Talent, Scene
from services.query.game_query_service import GameQueryService
from services.models.configs import HiringConfig
from services.calculation.role_performance_calculator import RolePerformanceCalculator
from services.calculation.talent_availability_checker import TalentAvailabilityChecker

logger = logging.getLogger(__name__)

class TalentDemandCalculator:
    def __init__(self, session_factory, data_manager: DataManager, query_service: GameQueryService,
                 config: HiringConfig, availability_checker: TalentAvailabilityChecker,
                 role_perf_calculator: RolePerformanceCalculator):
        self.session_factory = session_factory
        self.data_manager = data_manager
        self.query_service = query_service
        self.config = config
        self.availability_checker = availability_checker
        self.role_performance_calculator = role_perf_calculator
    
    def _calculate_base_multipliers(self, talent: Talent) -> float:
        """Calculates demand multipliers from talent's core stats (performance, ambition, popularity)."""
        performance_multiplier = 1 + (talent.performance / self.config.demand_perf_divisor)
        ambition_multiplier = 1.0 + ((talent.ambition - self.config.median_ambition) / self.config.ambition_demand_divisor)
        overall_popularity = sum(talent.popularity.values())
        popularity_multiplier = 1.0 + (overall_popularity * self.config.popularity_demand_scalar)
        return performance_multiplier * ambition_multiplier * popularity_multiplier

    def _calculate_role_modifier(self, scene: Scene, vp_id: int) -> float:
        """Calculates the demand modifier based on the most demanding role the VP plays."""
        max_demand_mod = 1.0
        action_segments_for_calc = scene.get_expanded_action_segments(self.data_manager.tag_definitions)
        for segment in action_segments_for_calc:
            if any(a.virtual_performer_id == vp_id for a in segment.slot_assignments):
                mod = self.role_performance_calculator.get_role_demand_modifier(segment, vp_id, scene, self.data_manager.tag_definitions)
                max_demand_mod = max(max_demand_mod, mod)
        return max_demand_mod

    def _calculate_preference_multiplier(self, talent: Talent, scene: Scene, vp_id: int) -> float:
        """Calculates the average preference score for the roles the VP plays."""
        _, roles_by_tag = self.availability_checker.get_vp_role_context(scene, vp_id)
        if not roles_by_tag:
            return 1.0
            
        preference_scores = []
        for tag_name, roles in roles_by_tag.items():
            for role in roles:
                score = talent.tag_preferences.get(tag_name, {}).get(role, 1.0)
                preference_scores.append(score)
        
        return np.mean(preference_scores) if preference_scores else 1.0

    def _calculate_travel_fee(self, talent: Talent, studio_location: str) -> int:
        """Calculates the travel fee for a talent based on their location vs. the studio's."""
        talent_location = talent.current_location
        if talent_location == studio_location:
            return 0

        location_map = self.data_manager.get_location_to_region_map()
        talent_region = location_map.get(talent_location)
        studio_region = location_map.get(studio_location)

        if talent_region and studio_region:
            if talent_region == studio_region:
                return self.config.location_to_location_cost
            if cost_data := self.data_manager.travel_matrix.get(talent_region, {}).get(studio_region):
                return cost_data.get('cost', 0)
        return 0

    def _calculate_base_demand(self, talent: Talent, scene: Scene, vp_id: int) -> int:
        """Calculates the base hiring cost (without travel) for a specific talent in a specific role, using pre-fetched data."""
        if not talent or not scene: return 0
        base_multipliers = self._calculate_base_multipliers(talent)
        role_modifier = self._calculate_role_modifier(scene, vp_id)
        preference_multiplier = self._calculate_preference_multiplier(talent, scene, vp_id)
        
        base_demand = self.config.base_talent_demand * base_multipliers * role_modifier
        
        # A preference > 1 reduces cost; a preference < 1 increases it.
        if preference_multiplier > 0:
            base_demand /= preference_multiplier
        
        return max(self.config.minimum_talent_demand, int(base_demand))

    def calculate_total_demand(self, talent_id: int, scene_id: int, vp_id: int,
                               studio_location: str, current_week: int, current_year: int, *,
                               scene: Optional[Scene] = None,
                               talent: Optional[Talent] = None) -> Dict[str, int]:
        """
        Calculates the total hiring cost for a single talent for a specific role.
        Returns a dictionary with a cost breakdown.
        """
        if talent is None:
            talent = self.query_service.get_talent_by_id(talent_id)
        if scene is None:
            scene = self.query_service.get_scene_for_planner(scene_id)

        base_cost = self._calculate_base_demand(talent, scene, vp_id)
        travel_fee = self._calculate_travel_fee(talent, studio_location) if talent else 0
        
        # Calculate Rush Fee if the scene is for the current week
        rush_fee = 0
        if scene and scene.scheduled_week == current_week and scene.scheduled_year == current_year:
            rush_fee = (base_cost + travel_fee) * (self.config.rush_fee_multiplier - 1.0)

        total_cost = base_cost + travel_fee + rush_fee

        return {
            "base_cost": int(base_cost),
            "travel_fee": int(travel_fee),
            "rush_fee": int(rush_fee),
            "total_cost": int(total_cost)
        }
    
    def calculate_demands_for_multiple_talents(self, talent_ids: List[int], scene_id: int, vp_id: int,
                                               studio_location: str, current_week: int, current_year: int) -> Dict[int, int]:
        """
        Efficiently calculates the total demand for a list of talents for a single role.
        Returns a dictionary mapping {talent_id: total_cost}.
        """
        if not talent_ids:
            return {}

        scene = self.query_service.get_scene_for_planner(scene_id)
        if not scene:
            return {}

        demands = {}
        talents_dc = self.query_service.get_multiple_talents_by_ids(talent_ids)

        for talent in talents_dc:
            cost_breakdown = self.calculate_total_demand(talent.id, scene_id, vp_id, studio_location, current_week, current_year, scene=scene, talent=talent)
            demands[talent.id] = cost_breakdown["total_cost"]

        return demands