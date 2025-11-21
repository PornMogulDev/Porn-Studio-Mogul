import logging
import numpy as np
from typing import List, Dict, Any

from data.data_manager import DataManager
from data.game_state import Talent, Scene
from services.models.configs import HiringConfig, ContractConfig
from services.calculation.role_performance_calculator import RolePerformanceCalculator
from services.calculation.talent_availability_checker import TalentAvailabilityChecker
from services.calculation.trait_modifier_resolver import TraitModifierResolver

logger = logging.getLogger(__name__)

class TalentDemandCalculator:
    """
    A pure, stateless calculator for determining talent hiring costs.
    It has no side effects and does not access the database. It relies
    on the caller to provide all necessary, pre-fetched data.
    """
    def __init__(self, data_manager: DataManager, hiring_config: HiringConfig,
                 contract_config: ContractConfig, availability_checker: TalentAvailabilityChecker,
                 role_perf_calculator: RolePerformanceCalculator, trait_resolver: TraitModifierResolver):
        self.data_manager = data_manager
        self.hiring_config = hiring_config
        self.contract_config = contract_config
        self.availability_checker = availability_checker
        self.role_performance_calculator = role_perf_calculator
        self.trait_resolver = trait_resolver
    
    def _calculate_base_multipliers(self, talent: Talent) -> float:
        """Calculates demand multipliers from talent's core stats (performance, ambition, popularity)."""
        performance_multiplier = 1 + (talent.performance / self.hiring_config.demand_perf_divisor)
        ambition_multiplier = 1.0 + ((talent.ambition - self.hiring_config.median_ambition) / self.hiring_config.ambition_demand_divisor)
        overall_popularity = sum(talent.popularity.values())
        popularity_multiplier = 1.0 + (overall_popularity * self.hiring_config.popularity_demand_scalar)
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

    def _calculate_travel_fee(self, talent: Talent, origin_location: str, destination_location: str) -> int:
        """Calculates the travel fee based on locations and trait modifiers."""
        if origin_location == destination_location:
            return 0

        base_fee = 0
        location_map = self.data_manager.get_location_to_region_map()
        origin_region = location_map.get(origin_location)
        destination_region = location_map.get(destination_location)

        if origin_region and destination_region:
            if origin_region == destination_region:
                base_fee = self.hiring_config.location_to_location_cost
            elif cost_data := self.data_manager.travel_matrix.get(origin_region, {}).get(destination_region):
                base_fee = cost_data.get('cost', 0)
        
        # Apply Trait Modifiers (e.g., "Globetrotter" = 0.5x, "Homebody" = 2.0x)
        trait_multiplier = self.trait_resolver.get_composite_modifier(talent, "travel_cost_multiplier")
        
        return int(base_fee * trait_multiplier)

    def _calculate_base_demand(self, talent: Talent, scene: Scene, vp_id: int) -> int:
        """Calculates the base hiring cost (without travel/hazard) for a specific talent in a specific role."""
        if not talent or not scene: return 0
        base_multipliers = self._calculate_base_multipliers(talent)
        role_modifier = self._calculate_role_modifier(scene, vp_id)
        preference_multiplier = self._calculate_preference_multiplier(talent, scene, vp_id)
        
        base_demand = self.hiring_config.base_talent_demand * base_multipliers * role_modifier
        
        # A preference > 1 reduces cost; a preference < 1 increases it.
        if preference_multiplier > 0:
            base_demand /= preference_multiplier

        # Contract Check: If talent has a contract, per-scene base cost is 0.
        if getattr(talent, 'contract', None):
             return 0
        
        return max(self.hiring_config.minimum_talent_demand, int(base_demand))

    def calculate_total_demand(self, talent: Talent, scene: Scene, vp_id: int,
                               talent_effective_location: str,
                               current_week: int, current_year: int) -> Dict[str, int]:
        """
        Calculates the total hiring cost for a single talent for a specific role.
        Includes Base, Travel, Rush Fee, and Hazard Pay (D/S Intensity).
        """
        # 1. Calculate Base Demand (Performance, Popularity, Role fit)
        base_cost = self._calculate_base_demand(talent, scene, vp_id)
        
        # 2. Calculate Hazard Pay (D/S Intensity vs Preference)
        # Formula: Adjusted = Base * (Hazard_Level_Mod / Talent_Pref_Level_Mod)
        ds_level = scene.dom_sub_dynamic_level
        hazard_mod = self.hiring_config.hazard_pay_modifiers.get(ds_level, 1.0)
        
        # Use trait resolver? No, DS prefs are on the talent object directly.
        # Fallback to 1.0 if key missing
        talent_pref = talent.ds_dynamic_preferences.get(ds_level, 1.0)
        
        # Prevent division by zero
        if talent_pref <= 0: talent_pref = 0.1
            
        # Combined multiplier for intensity
        intensity_multiplier = hazard_mod / talent_pref
        
        ds_adjusted_base = base_cost * intensity_multiplier
        hazard_pay = ds_adjusted_base - base_cost

        # 3. Calculate Travel
        travel_fee = self._calculate_travel_fee(talent, talent_effective_location, scene.location)
        
        # 4. Calculate Rush Fee (applies to base + hazard + travel)
        rush_fee = 0
        if scene.scheduled_week == current_week and scene.scheduled_year == current_year:
            rush_fee = (ds_adjusted_base + travel_fee) * (self.hiring_config.rush_fee_multiplier - 1.0)

        total_cost = ds_adjusted_base + travel_fee + rush_fee

        return {
            "base_cost": int(base_cost),
            "hazard_pay": int(hazard_pay), # Logic adjustment for display
            "travel_fee": int(travel_fee),
            "rush_fee": int(rush_fee),
            "total_cost": int(total_cost)
        }
    
    def calculate_contract_salary(self, talent: Talent, conditions: Dict[str, Any]) -> int:
        """
        Calculates the weekly salary for an exclusive contract.
        Factors in:
        - Content scope (allowed tags)
        - D/S Intensity limit (max_dynamic)
        - Traits (contract_salary_multiplier)
        """
        allowed_concepts = set(conditions.get('allowed_concepts', []))
        allowed_orientations = set(conditions.get('allowed_orientations', []))
        
        relevant_tags = []
        
        # 1. Identify all tags covered by this contract
        for tag_key, tag_def in self.data_manager.tag_definitions.items():
            tag_concept = tag_def.get('concept')
            tag_orientation = tag_def.get('orientation')
            
            if tag_concept not in allowed_concepts: continue
            if tag_orientation and tag_orientation not in allowed_orientations: continue
                
            relevant_tags.append(tag_key)

        if not relevant_tags:
            return int(self.hiring_config.minimum_talent_demand * self.contract_config.fallback_salary_multiplier)

        # 2. Calculate average preference multiplier for these tags
        base_demand = self.hiring_config.base_talent_demand * self._calculate_base_multipliers(talent)
        
        pref_sum = 0.0
        for tag_name in relevant_tags:
            role_prefs = talent.tag_preferences.get(tag_name, {}).values()
            if role_prefs:
                pref_sum += max(role_prefs)
            else:
                pref_sum += 1.0
        
        avg_preference = pref_sum / len(relevant_tags) if relevant_tags else 1.0
        
        # 3. D/S Intensity Adjustment
        # If contract allows up to Level 3, we verify their comfort with Level 3.
        max_dynamic = conditions.get('max_dynamic', 3)
        
        # We look at the worst-case scenario for the talent within that range.
        # If they love Level 0 (1.5) but hate Level 3 (0.5), and max is 3, 
        # they will demand pay based on Level 3.
        min_ds_pref = 99.0
        max_hazard_mod = 1.0
        
        for level in range(max_dynamic + 1):
            pref = talent.ds_dynamic_preferences.get(level, 1.0)
            if pref < min_ds_pref: min_ds_pref = pref
            
            hazard = self.hiring_config.hazard_pay_modifiers.get(level, 1.0)
            if hazard > max_hazard_mod: max_hazard_mod = hazard

        if min_ds_pref <= 0: min_ds_pref = 0.1
        
        # Multiplier based on the most "dangerous" allowed intensity vs their lowest preference for it
        ds_intensity_multiplier = max_hazard_mod / min_ds_pref

        # 4. Apply Logic
        adjusted_base = base_demand / max(self.contract_config.preference_salary_floor, avg_preference)
        adjusted_base *= ds_intensity_multiplier # Apply D/S scaling
        
        # 5. Apply Trait Modifiers (e.g. "Greedy", "Commitment Phobe")
        trait_multiplier = self.trait_resolver.get_composite_modifier(talent, "contract_salary_multiplier")
        adjusted_base *= trait_multiplier

        # 6. Lock-in and Scale
        max_scenes = conditions.get('max_scenes_per_week', 1)
        contract_premium = self.contract_config.lock_in_premium
        
        weekly_salary = adjusted_base * max_scenes * contract_premium
        
        return int(max(self.hiring_config.minimum_talent_demand, weekly_salary))

    def calculate_bulk_hiring_costs(self, talent: Talent,
                                    roles_with_context: List[Dict[str, Any]],
                                    current_week: int, current_year: int) -> Dict:
        """
        Calculates authoritative costs for a bulk hiring transaction.
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
            bloc_id = role['bloc_id'] if role['bloc_id'] is not None else f"nobloc_{role['scene'].id}"
            bloc_groups[bloc_id].append(role)

        # 3. Calculate upfront travel and final salaries for each bloc
        total_upfront_cost = sum(r['travel_fee'] for r in roles_with_costs)
        final_role_salaries = []

        for _, bloc_roles in bloc_groups.items():
            num_roles = len(bloc_roles)
            discount_multiplier = self.hiring_config.bulk_discount_tiers.get(num_roles, 1.0)

            # Base for discount includes the base demand + hazard pay, but not travel/rush
            total_bloc_salary_basis = sum(r['base_cost'] + r['hazard_pay'] for r in bloc_roles)
            discounted_basis = total_bloc_salary_basis * discount_multiplier

            for role in bloc_roles:
                role_basis = role['base_cost'] + role['hazard_pay']
                proportion = role_basis / total_bloc_salary_basis if total_bloc_salary_basis > 0 else 0
                
                final_salary_portion = discounted_basis * proportion

                # Final salary is the discounted salary basis + any non-discounted fees (rush fee)
                final_salary = final_salary_portion + role['rush_fee']

                final_role_salaries.append({
                    'scene_id': role['scene'].id,
                    'virtual_performer_id': role['virtual_performer_id'],
                    'final_salary': int(final_salary)
                })

        return {"total_upfront_cost": total_upfront_cost, "roles_with_final_salaries": final_role_salaries}