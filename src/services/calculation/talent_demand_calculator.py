import logging
import numpy as np
from typing import List, Dict, Any

from data.data_manager import DataManager
from data.game_state import Talent, Scene
from services.models.configs import HiringConfig
from services.calculation.role_performance_calculator import RolePerformanceCalculator
from services.calculation.talent_availability_checker import TalentAvailabilityChecker

logger = logging.getLogger(__name__)

class TalentDemandCalculator:
    """
    A pure, stateless calculator for determining talent hiring costs.
    It has no side effects and does not access the database. It relies
    on the caller to provide all necessary, pre-fetched data.
    """
    def __init__(self, data_manager: DataManager, config: HiringConfig,
                 availability_checker: TalentAvailabilityChecker,
                 role_perf_calculator: RolePerformanceCalculator):
        self.data_manager = data_manager
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

    def get_role_preference_score(self, talent: Talent, scene: Scene, vp_id: int) -> float:
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
    
    def _calculate_preference_multiplier(self, talent: Talent, scene: Scene, vp_id: int) -> float:
        return self.get_role_preference_score(talent, scene, vp_id)

    def _calculate_travel_fee(self, origin_location: str, destination_location: str) -> int:
        """Calculates the travel fee based on origin and destination locations."""
        if origin_location == destination_location:
            return 0

        location_map = self.data_manager.get_location_to_region_map()
        origin_region = location_map.get(origin_location)
        destination_region = location_map.get(destination_location)

        if origin_region and destination_region:
            if origin_region == destination_region:
                return self.config.location_to_location_cost
            if cost_data := self.data_manager.travel_matrix.get(origin_region, {}).get(destination_region):
                return cost_data.get('cost', 0)
        return 0

    def _calculate_base_demand(self, talent: Talent, scene: Scene, vp_id: int) -> int:
        """Calculates the base hiring cost (without travel) for a specific talent in a specific role."""
        if not talent or not scene: return 0
        base_multipliers = self._calculate_base_multipliers(talent)
        role_modifier = self._calculate_role_modifier(scene, vp_id)
        preference_multiplier = self._calculate_preference_multiplier(talent, scene, vp_id)
        
        base_demand = self.config.base_talent_demand * base_multipliers * role_modifier
        
        # A preference > 1 reduces cost; a preference < 1 increases it.
        if preference_multiplier > 0:
            base_demand /= preference_multiplier

        # Contract Check: If talent has a contract, per-scene base cost is 0.
        if getattr(talent, 'contract', None):
             return 0
        
        return max(self.config.minimum_talent_demand, int(base_demand))

    def calculate_total_demand(self, talent: Talent, scene: Scene, vp_id: int,
                               talent_effective_location: str,
                               current_week: int, current_year: int) -> Dict[str, int]:
        """
        Calculates the total hiring cost for a single talent for a specific role.
        This method is pure and relies on the caller to provide all data.

        Args:
            talent: The Talent dataclass.
            scene: The Scene dataclass.
            vp_id: The ID of the virtual performer for the role.
            talent_effective_location: The talent's location on the scene's date,
                                       as determined by the TalentLocationService.
            current_week: The game's current week.
            current_year: The game's current year.

        Returns:
            A dictionary with a cost breakdown.
        """
        base_cost = self._calculate_base_demand(talent, scene, vp_id)
        
        travel_fee = self._calculate_travel_fee(talent_effective_location, scene.location)
        
        # Calculate Rush Fee if the scene is for the current week
        rush_fee = 0
        if scene.scheduled_week == current_week and scene.scheduled_year == current_year:
            # Rush fee applies to the cost of getting the talent there, not just their salary.
            rush_fee = (base_cost + travel_fee) * (self.config.rush_fee_multiplier - 1.0)

        total_cost = base_cost + travel_fee + rush_fee

        return {
            "base_cost": int(base_cost),
            "travel_fee": int(travel_fee),
            "rush_fee": int(rush_fee),
            "total_cost": int(total_cost)
        }
    
    def calculate_contract_salary(self, talent: Talent, conditions: Dict[str, Any]) -> int:
        """
        Calculates the weekly salary for an exclusive contract based on the breadth
        of the terms and the talent's affinity for those terms.
        """
        allowed_concepts = set(conditions.get('allowed_concepts', []))
        allowed_orientations = set(conditions.get('allowed_orientations', []))
        
        relevant_tags = []
        
        # 1. Identify all tags covered by this contract
        # We iterate items() to get the full unique key (e.g. "Blowjob (Straight)")
        # which matches the keys stored in the talent's tag_preferences.
        for tag_key, tag_def in self.data_manager.tag_definitions.items():
            tag_concept = tag_def.get('concept')
            tag_orientation = tag_def.get('orientation')
            
            # Rule 1: If a concept is unchecked, remove all tags contained in that concept
            if tag_concept not in allowed_concepts:
                continue
            
            # Rule 2: If an orientation is unchecked, remove all tags with that orientation
            # (Tags with NO orientation, like costumes, are kept unless the Concept was removed)
            if tag_orientation and tag_orientation not in allowed_orientations:
                continue
                
            relevant_tags.append(tag_key)

        if not relevant_tags:
            # If they uncheck everything, return a fallback or minimum
            return self.config.minimum_talent_demand * 5 # Fallback

        # 2. Calculate average preference multiplier for these tags
        
        base_demand = self.config.base_talent_demand * self._calculate_base_multipliers(talent)
        
        # Calculate average preference modifier for the specific subset of tags allowed
        pref_sum = 0.0
        for tag_name in relevant_tags:
            # Get the highest preference among all roles for this tag (optimistic)
            role_prefs = talent.tag_preferences.get(tag_name, {}).values()
            if role_prefs:
                pref_sum += max(role_prefs)
            else:
                pref_sum += 1.0
        
        avg_preference = pref_sum / len(relevant_tags) if relevant_tags else 1.0
        
        # Demand Formula: Cost increases if the talent dislikes the allowed content (avg < 1.0).
        # Cost decreases if the talent loves the allowed content (avg > 1.0).
        adjusted_base = base_demand / max(0.1, avg_preference)
        
        # Apply Lock-in Premium (e.g. 1.5x standard rate because they can't work elsewhere)
        # And scale by max scenes per week
        max_scenes = conditions.get('max_scenes_per_week', 1)
        contract_premium = 1.5 
        
        # Weekly salary covers the potential of 'max_scenes' shoots
        weekly_salary = adjusted_base * max_scenes * contract_premium
        
        return int(max(self.config.minimum_talent_demand, weekly_salary))

    def calculate_bulk_hiring_costs(self, talent: Talent,
                                    roles_with_context: List[Dict[str, Any]],
                                    current_week: int, current_year: int) -> Dict:
        """
        Calculates authoritative costs for a bulk hiring transaction, applying tiered discounts.
        This method is pure and relies on the caller to provide all data.

        Args:
            talent: The Talent dataclass.
            roles_with_context: A list of dictionaries, where each dict contains:
                                'scene': The Scene dataclass.
                                'virtual_performer_id': The VP ID for the role.
                                'bloc_id': The bloc ID for the scene.
                                'talent_effective_location': Talent's location for this scene's date.
            current_week: The game's current week.
            current_year: The game's current year.

        Returns:
            A dictionary breakdown of upfront costs and final deferred salaries.
        """
        from collections import defaultdict

        # 1. Get cost breakdown for each role using the single-role calculator
        roles_with_costs = []
        for role_context in roles_with_context:
            cost_breakdown = self.calculate_total_demand(
                talent, role_context['scene'], role_context['virtual_performer_id'],
                role_context['talent_effective_location'], current_week, current_year
            )
            roles_with_costs.append({**role_context, **cost_breakdown})

        # 2. Group roles by bloc
        bloc_groups = defaultdict(list)
        for role in roles_with_costs:
            # Group scenes without a bloc individually to prevent incorrect discounts
            bloc_id = role['bloc_id'] if role['bloc_id'] is not None else f"nobloc_{role['scene'].id}"
            bloc_groups[bloc_id].append(role)

        # 3. Calculate upfront travel and final salaries for each bloc
        total_upfront_cost = sum(r['travel_fee'] for r in roles_with_costs)
        final_role_salaries = []

        for _, bloc_roles in bloc_groups.items():
            num_roles = len(bloc_roles)
            discount_multiplier = self.config.bulk_discount_tiers.get(num_roles, 1.0)

            total_bloc_base_cost = sum(r['base_cost'] for r in bloc_roles)
            discounted_total_bloc_base_cost = total_bloc_base_cost * discount_multiplier

            for role in bloc_roles:
                # Distribute discount proportionally based on the role's contribution to the bloc's base cost
                proportion = role['base_cost'] / total_bloc_base_cost if total_bloc_base_cost > 0 else 0
                final_base_salary = discounted_total_bloc_base_cost * proportion

                # Final salary is the discounted base + any non-discounted fees (rush fee)
                final_salary = final_base_salary + role['rush_fee']

                final_role_salaries.append({
                    'scene_id': role['scene'].id,
                    'virtual_performer_id': role['virtual_performer_id'],
                    'final_salary': int(final_salary)
                })

        return {"total_upfront_cost": total_upfront_cost, "roles_with_final_salaries": final_role_salaries}