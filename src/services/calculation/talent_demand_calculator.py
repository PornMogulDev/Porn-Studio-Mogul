import logging
from typing import List, Dict, Any, Optional, Set
import numpy as np

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
        
        trait_multiplier = self.trait_resolver.get_composite_modifier(talent, "travel_cost_multiplier")
        
        return int(base_fee * trait_multiplier)

    def _calculate_base_demand(self, talent: Talent, scene: Scene, vp_id: int) -> int:
        """Calculates the base hiring cost (without travel/hazard) for a specific talent in a specific role."""
        if not talent or not scene: return 0
        base_multipliers = self._calculate_base_multipliers(talent)
        role_modifier = self._calculate_role_modifier(scene, vp_id)
        preference_multiplier = self._calculate_preference_multiplier(talent, scene, vp_id)
        
        base_demand = self.hiring_config.base_talent_demand * base_multipliers * role_modifier
        
        if preference_multiplier > 0:
            base_demand /= preference_multiplier

        if getattr(talent, 'contract', None):
             return 0
        
        return max(self.hiring_config.minimum_talent_demand, int(base_demand))

    def calculate_total_demand(self, talent: Talent, scene: Scene, vp_id: int,
                               talent_effective_location: str,
                               current_absolute_week: int,
                               existing_bloc_ids: Set[int] = None) -> Dict[str, int]:
        """
        Calculates the total hiring cost for a single talent for a specific role.
        
        Args:
            existing_bloc_ids: Optional set of bloc IDs the talent is already booked for.
                               If the scene's bloc ID is in this set, travel fee is waived.
        """
        base_cost = self._calculate_base_demand(talent, scene, vp_id)
        
        ds_level = scene.dom_sub_dynamic_level
        hazard_mod = self.hiring_config.hazard_pay_modifiers.get(ds_level, 1.0)
        talent_pref = talent.ds_dynamic_preferences.get(ds_level, 1.0)
        if talent_pref <= 0: talent_pref = 0.1
        intensity_multiplier = hazard_mod / talent_pref
        ds_adjusted_base = base_cost * intensity_multiplier
        hazard_pay = ds_adjusted_base - base_cost

        # Logistics Logic: Check if travel is required for this specific booking
        travel_fee = 0
        
        # If the scene belongs to a bloc the talent is already booked for, assume they are there.
        # Otherwise, calculate travel normally.
        requires_new_travel = True
        if existing_bloc_ids and scene.bloc_id in existing_bloc_ids:
            requires_new_travel = False
            
        if requires_new_travel:
            travel_fee = self._calculate_travel_fee(talent, talent_effective_location, scene.location)
        
        rush_fee = 0
        if scene.scheduled_absolute_week == current_absolute_week:
            rush_fee = (ds_adjusted_base + travel_fee) * (self.hiring_config.rush_fee_multiplier - 1.0)

        total_cost = ds_adjusted_base + travel_fee + rush_fee

        return {
            "base_cost": int(base_cost),
            "hazard_pay": int(hazard_pay),
            "travel_fee": int(travel_fee),
            "rush_fee": int(rush_fee),
            "total_cost": int(total_cost)
        }
    
    def _calculate_disposition_salary_modifier(self, talent: Talent, req_disposition: Optional[str]) -> float:
        """
        Calculates a salary multiplier based on how well the talent fits the 
        required disposition (Dom/Sub/Switch) of the contract.
        """
        if not req_disposition or req_disposition == "Any":
            return 1.0

        # Weights
        w_disp = self.contract_config.disposition_salary_weight
        w_skill = self.contract_config.skill_salary_weight

        # Normalize Data to 0.0 - 1.0 range (or -1.0 to 1.0 for disposition)
        norm_disp = talent.disposition_score / 100.0  # Range: -1.0 (Sub) to 1.0 (Dom)
        norm_dom_skill = talent.dom_skill / 100.0     # Range: 0.0 to 1.0
        norm_sub_skill = talent.sub_skill / 100.0     # Range: 0.0 to 1.0
        
        mismatch_score = 0.0 # 0.0 = Perfect Fit, 1.0 = Complete Mismatch

        if req_disposition == "Dom":
            # Ideal: Disposition 1.0, Dom Skill 1.0
            # Calculate mismatch based on distance from Ideal
            
            # Disp Mismatch: (1.0 - score) / 2. 
            # e.g., if score is 1.0, mismatch is 0. If score is -1.0, mismatch is 1.0.
            disp_mismatch = (1.0 - norm_disp) / 2.0
            skill_mismatch = 1.0 - norm_dom_skill
            
            mismatch_score = (w_disp * disp_mismatch) + (w_skill * skill_mismatch)

        elif req_disposition == "Sub":
            # Ideal: Disposition -1.0, Sub Skill 1.0
            
            # Disp Mismatch: (score - (-1.0)) / 2 -> (score + 1.0) / 2.
            # e.g., if score is -1.0, mismatch is 0. If score is 1.0, mismatch is 1.0.
            disp_mismatch = (norm_disp + 1.0) / 2.0
            skill_mismatch = 1.0 - norm_sub_skill
            
            mismatch_score = (w_disp * disp_mismatch) + (w_skill * skill_mismatch)

        elif req_disposition == "Switch":
            # Ideal: Disposition 0.0, Avg(Dom+Sub) Skill 1.0
            
            # Disp Mismatch: Absolute distance from 0
            disp_mismatch = abs(norm_disp)
            
            # Skill Mismatch: Inverse of average skills
            avg_skill = (norm_dom_skill + norm_sub_skill) / 2.0
            skill_mismatch = 1.0 - avg_skill
            
            mismatch_score = (w_disp * disp_mismatch) + (w_skill * skill_mismatch)

        # Convert Mismatch Score to Salary Multiplier.
        # Perfect fit (0.0) -> 0.9x (Discount for doing what they love)
        # Worst fit (1.0) -> 2.5x (High premium for forcing character break)
        
        base_mult = 0.9
        penalty_slope = 1.6 # 0.9 + 1.6 = 2.5
        
        return base_mult + (mismatch_score * penalty_slope)

    def calculate_contract_salary(self, talent: Talent, conditions: Dict[str, Any]) -> int:
        """
        Calculates the weekly salary for an exclusive contract.
        Includes calculations for preference match, intensity limits, and disposition match.
        """
        allowed_concepts = set(conditions.get('allowed_concepts', []))
        allowed_orientations = set(conditions.get('allowed_orientations', []))
        req_disposition = conditions.get('disposition') # "Dom", "Sub", "Switch", or None
        
        relevant_tags = []
        
        for tag_key, tag_def in self.data_manager.tag_definitions.items():
            tag_concept = tag_def.get('concept')
            tag_orientation = tag_def.get('orientation')
            
            if tag_concept not in allowed_concepts: continue
            if tag_orientation and tag_orientation not in allowed_orientations: continue
                
            relevant_tags.append(tag_key)

        if not relevant_tags:
            return int(self.hiring_config.minimum_talent_demand * self.contract_config.fallback_salary_multiplier)

        base_demand = self.hiring_config.base_talent_demand * self._calculate_base_multipliers(talent)
        
        pref_sum = 0.0
        for tag_name in relevant_tags:
            role_prefs = talent.tag_preferences.get(tag_name, {}).values()
            if role_prefs:
                pref_sum += max(role_prefs)
            else:
                pref_sum += 1.0
        
        avg_preference = pref_sum / len(relevant_tags) if relevant_tags else 1.0
        
        max_dynamic = conditions.get('max_dynamic', 3)
        min_ds_pref = 99.0
        max_hazard_mod = 1.0
        
        for level in range(max_dynamic + 1):
            pref = talent.ds_dynamic_preferences.get(level, 1.0)
            if pref < min_ds_pref: min_ds_pref = pref
            
            hazard = self.hiring_config.hazard_pay_modifiers.get(level, 1.0)
            if hazard > max_hazard_mod: max_hazard_mod = hazard

        if min_ds_pref <= 0: min_ds_pref = 0.1
        
        ds_intensity_multiplier = max_hazard_mod / min_ds_pref

        # Disposition Mismatch Calculation
        disposition_multiplier = self._calculate_disposition_salary_modifier(talent, req_disposition)

        # Formula Application
        adjusted_base = base_demand / max(self.contract_config.preference_salary_floor, avg_preference)
        adjusted_base *= ds_intensity_multiplier
        adjusted_base *= disposition_multiplier # Apply new modifier
        
        trait_multiplier = self.trait_resolver.get_composite_modifier(talent, "contract_salary_multiplier")
        adjusted_base *= trait_multiplier

        max_scenes = conditions.get('max_scenes_per_week', 1)
        contract_premium = self.contract_config.lock_in_premium
        
        weekly_salary = adjusted_base * max_scenes * contract_premium
        
        return int(max(self.hiring_config.minimum_talent_demand, weekly_salary))


    def calculate_bulk_hiring_costs(self, talent: Talent,
                                    roles_with_context: List[Dict[str, Any]],
                                    current_absolute_week: int,
                                    existing_bloc_ids: Set[int] = None) -> Dict:
        """
        Calculates authoritative costs for a bulk hiring transaction.
        Handles per-bloc travel fees incrementally.
        
        Args:
            existing_bloc_ids: Set of bloc IDs the talent is already booked for.
        """
        from collections import defaultdict
        
        # Track which blocs we have already "paid" for in this calculation chain.
        # We start with what's already in the DB.
        covered_blocs = set(existing_bloc_ids) if existing_bloc_ids else set()

        roles_with_costs = []
        for role_context in roles_with_context:
            scene = role_context['scene']
            
            # Calculate cost for this specific role, passing in our running set of covered blocs
            # Note: We must pass a COPY or be careful, but since calculate_total_demand doesn't modify the set,
            # we can pass `covered_blocs`. However, calculate_total_demand is stateless. 
            # It just calculates. We need to manually update our covered set here for the NEXT iteration.
            
            cost_breakdown = self.calculate_total_demand(
                talent, scene, role_context['virtual_performer_id'],
                role_context['talent_effective_location'], current_absolute_week,
                covered_blocs
            )
            
            # If this calculation resulted in a travel fee > 0, it means we just "paid" for this bloc.
            # Add it to covered_blocs so the next scene in this loop gets it free.
            # Even if travel was 0 (e.g. local), we add it, so we are consistent.
            if scene.bloc_id:
                covered_blocs.add(scene.bloc_id)
                
            roles_with_costs.append({**role_context, **cost_breakdown})

        # Calculate Bulk Discounts on Salaries (Upfront travel costs are never discounted)
        bloc_groups = defaultdict(list)
        for role in roles_with_costs:
            bloc_id = role['bloc_id'] if role['bloc_id'] is not None else f"nobloc_{role['scene'].id}"
            bloc_groups[bloc_id].append(role)

        total_upfront_cost = sum(r['travel_fee'] for r in roles_with_costs)
        final_role_salaries = []

        for _, bloc_roles in bloc_groups.items():
            num_roles = len(bloc_roles)
            discount_multiplier = self.hiring_config.bulk_discount_tiers.get(str(num_roles), 1.0)

            total_bloc_salary_basis = sum(r['base_cost'] + r['hazard_pay'] for r in bloc_roles)
            discounted_basis = total_bloc_salary_basis * discount_multiplier

            for role in bloc_roles:
                role_basis = role['base_cost'] + role['hazard_pay']
                proportion = role_basis / total_bloc_salary_basis if total_bloc_salary_basis > 0 else 0
                
                final_salary_portion = discounted_basis * proportion
                final_salary = final_salary_portion + role['rush_fee']

                final_role_salaries.append({
                    'scene_id': role['scene'].id,
                    'virtual_performer_id': role['virtual_performer_id'],
                    'final_salary': int(final_salary)
                })

        return {"total_upfront_cost": total_upfront_cost, "roles_with_final_salaries": final_role_salaries}