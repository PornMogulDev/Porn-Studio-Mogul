import logging
import numpy as np
from typing import Optional, Tuple
from sqlalchemy.orm import joinedload

from data.data_manager import DataManager
from data.game_state import Talent, Scene
from database.db_models import SceneDB, ActionSegmentDB
from services.query.game_query_service import GameQueryService
from services.models.configs import HiringConfig
from services.calculation.role_performance_calculator import RolePerformanceCalculator
from services.calculation.talent_availability_checker import TalentAvailabilityChecker

logger = logging.getLogger(__name__)

class TalentDemandCalculator:
    def __init__(self, session_factory, data_manager: DataManager, query_service: GameQueryService,
                 config: HiringConfig, availability_checker: TalentAvailabilityChecker):
        self.session_factory = session_factory
        self.data_manager = data_manager
        self.query_service = query_service
        self.config = config
        self.availability_checker = availability_checker
    
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
            slots = scene._get_slots_for_segment(segment, self.data_manager.tag_definitions)
            for assignment in segment.slot_assignments:
                if assignment.virtual_performer_id == vp_id:
                    try: 
                        _, role, _ = assignment.slot_id.rsplit('_', 2)
                    except ValueError: 
                        continue
                    slot_def = next((s for s in slots if s['role'] == role), None)
                    if not slot_def: 
                        continue
                    final_mod = RolePerformanceCalculator.get_final_modifier('demand_modifier', slot_def, segment, role)
                    max_demand_mod = max(max_demand_mod, final_mod)
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

    def calculate_travel_fee(self, talent: Talent, studio_location: str) -> int:
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

    def calculate_talent_demand(self, talent_id: int, scene_id: int, vp_id: int, scene: Optional[Scene] = None) -> int:
        """Calculates the base hiring cost (without travel) for a specific talent in a specific role."""
        session = self.session_factory()
        try:
            talent = self.query_service.get_talent_by_id(talent_id)
            if not talent: return 0

            if not scene:
                scene_db = self.query_service.get_scene_db_for_casting(session, scene_id)
                if not scene_db: return 0
                scene = scene_db.to_dataclass(Scene)

            base_multipliers = self._calculate_base_multipliers(talent)
            role_modifier = self._calculate_role_modifier(scene, vp_id)
            preference_multiplier = self._calculate_preference_multiplier(talent, scene, vp_id)
            
            base_demand = self.config.base_talent_demand * base_multipliers * role_modifier
            
            # A preference > 1 reduces cost; a preference < 1 increases it.
            if preference_multiplier > 0:
                base_demand /= preference_multiplier

            return max(self.config.minimum_talent_demand, int(base_demand))
        except Exception as e:
            logger.error(f"Error calculating demand for talent {talent_id} in scene {scene_id}: {e}", exc_info=True)
            return 0
        finally:
            session.close()