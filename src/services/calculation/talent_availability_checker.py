import random
from dataclasses import dataclass
from collections import defaultdict
from typing import Set, Dict, Optional, Union, List

from data.game_state import Talent, Scene
from database.db_models import TalentDB, ShootingBlocDB
from data.data_manager import DataManager
from services.models.configs import HiringConfig

@dataclass(frozen=True)
class AvailabilityResult:
    """Represents the outcome of a talent availability check."""
    is_available: bool
    reason: Optional[str] = None

class TalentAvailabilityChecker:
    """
    A pure, stateless logic class that encapsulates the complex business rules 
    for checking if a talent is available and willing to perform a specific role.

    This class centralizes all "will they do it?" checks, including:
    - Scheduling and fatigue limits
    - Scene content (partners, hard limits, concurrency)
    - Personal preferences and orientation
    - Production budget and quality standards
    - Studio policies
    - Strict contract constraints

    It is instantiated by services and has no side effects. The calling service
    (e.g., `TalentQueryService`) is responsible for fetching all required data
    and passing it to the `check` method.
    """
    def __init__(self, data_manager: DataManager, config: HiringConfig):
        self.data_manager = data_manager
        self.config = config

    def get_vp_role_context(self, scene: Scene, vp_id: int) -> tuple[Set[str], Dict[str, Set[str]]]:
        """
        Parses the scene's expanded segments once to extract all action tags and
        the specific roles a virtual performer (VP) has within those tags.

        This is a crucial helper used by multiple checks to understand what a
        talent is actually being asked to do in a scene.

        Returns:
            A tuple containing:
            - A set of all action tag names the VP participates in.
            - A dictionary mapping each action tag to a set of roles the VP has in that tag.
              e.g., `{'Blowjob (Straight)': {'Giver'}, 'Anal Sex': {'Giver', 'Receiver'}}`
        """
        action_tags = set()
        roles_by_tag = defaultdict(set)
        
        expanded_segments = scene.get_expanded_action_segments(self.data_manager.tag_definitions)
        for segment in expanded_segments:
            is_vp_in_segment = False
            for assignment in segment.slot_assignments:
                if assignment.virtual_performer_id == vp_id:
                    is_vp_in_segment = True
                    try:
                        # Assumes slot_id format like "ActionTagName_RoleName_Number"
                        _, role, _ = assignment.slot_id.rsplit('_', 2)
                    except ValueError:
                        role = "Performer" # Default fallback role
                    roles_by_tag[segment.tag_name].add(role)
            
            if is_vp_in_segment:
                action_tags.add(segment.tag_name)
                
        return action_tags, dict(roles_by_tag)

    def _check_schedule_and_fatigue(self, talent: Union[Talent, TalentDB], bookings_before: List[Scene], 
                                bookings_current: List[Scene], bookings_after: List[Scene], 
                                estimated_fatigue_gain: int) -> AvailabilityResult:
        """Checks for weekly workload limits and projected fatigue, including burnout risk."""
        burnout_penalty = 0
        # A talent is considered at risk of burnout if they are booked for three consecutive weeks.
        # This imposes a penalty, reducing the number of scenes they are willing to do in the middle week.
        if bookings_before and bookings_after:
            burnout_penalty = self.config.burnout_penalty_scenes

        # Check 1: Max Scenes Per Week
        # A talent's ambition modifies their base willingness to take on more work.
        ambition_bonus = (talent.ambition - self.config.median_ambition) * self.config.max_scenes_per_week_ambition_modifier
        base_max_scenes = round(self.config.max_scenes_per_week_base + ambition_bonus)
        
        # Apply the burnout penalty
        effective_max_scenes = max(1, base_max_scenes - burnout_penalty)

        if len(bookings_current) >= effective_max_scenes:
            reason = f"Will not shoot more than {effective_max_scenes} scenes in one week."
            if burnout_penalty > 0:
                reason += " (Avoiding burnout)"
            return AvailabilityResult(False, reason)

        # Check 2: Fatigue Projection
        # A talent will refuse a role if the estimated fatigue gain from it would push
        # their total fatigue over a critical threshold.
        projected_total_fatigue = talent.fatigue + estimated_fatigue_gain
        if projected_total_fatigue > self.config.fatigue_refusal_threshold:
            return AvailabilityResult(False, "Refuses work that would cause extreme fatigue.")

        return AvailabilityResult(is_available=True)

    def _check_max_partners(self, talent: Union[Talent, TalentDB], scene: Scene) -> AvailabilityResult:
        """Checks if the scene exceeds the talent's partner limit."""
        num_performers = len(scene.virtual_performers)
        # The number of "partners" is everyone else in the scene.
        if num_performers > 1 and (num_performers - 1) > talent.max_scene_partners:
            return AvailabilityResult(False, f"Refuses scenes with more than {talent.max_scene_partners} partners.")
        return AvailabilityResult(is_available=True)

    def _check_hard_limits(self, talent: Union[Talent, TalentDB], role_action_tags: Set[str]) -> AvailabilityResult:
        """Checks if the role involves any of the talent's hard limits."""
        for full_tag_name in role_action_tags:
            tag_def = self.data_manager.tag_definitions.get(full_tag_name)
            base_name = tag_def.get('name') if tag_def else full_tag_name
            # Check against both the full name (e.g., "Anal Sex (M/F)") and the base name ("Anal Sex")
            if full_tag_name in talent.hard_limits or (base_name and base_name in talent.hard_limits):
                return AvailabilityResult(False, f"Talent has a hard limit against '{base_name}'.")
        return AvailabilityResult(is_available=True)

    def _check_concurrency_limits(self, talent: Union[Talent, TalentDB], scene: Scene, vp_id: int, roles_by_tag: Dict[str, Set[str]]) -> AvailabilityResult:
        """
        Checks for violations of concurrent partner limits (e.g., refusing DP).
        This rule applies when a talent is a 'Receiver' for a concept and checks
        if the number of 'Giver' partners exceeds their personal limit for that concept.
        """
        expanded_segments = scene.get_expanded_action_segments(self.data_manager.tag_definitions)
        for segment in expanded_segments:
            # Skip segments the current VP isn't in
            if not any(a.virtual_performer_id == vp_id for a in segment.slot_assignments):
                continue
            
            tag_def = self.data_manager.tag_definitions.get(segment.tag_name)
            if not tag_def or not (concept := tag_def.get('concept')):
                continue
            
            # This check only applies if the talent is a 'Receiver' in the current action
            if 'Receiver' in roles_by_tag.get(segment.tag_name, set()):
                # Count the number of 'Giver' roles in this specific segment
                num_givers = sum(1 for a in segment.slot_assignments if '_Giver_' in a.slot_id)
                limit = talent.concurrency_limits.get(concept, self.config.concurrency_default_limit)
                if num_givers > limit:
                    return AvailabilityResult(False, f"Concurrency limit for '{concept}' exceeded (Max: {limit}, Scene has: {num_givers}).")
        return AvailabilityResult(is_available=True)

    def _check_preferences(self, talent: Union[Talent, TalentDB], roles_by_tag: Dict[str, Set[str]]) -> AvailabilityResult:
        """
        Checks if the role is acceptable based on preferences and orientation.
        A talent will refuse a role if their preference score for it is below a
        certain threshold. A lower threshold exists for orientation-related conflicts,
        resulting in a more specific refusal reason.
        """
        refusal_threshold = self.config.refusal_threshold
        orientation_threshold = self.config.orientation_refusal_threshold
        for tag_name, roles_in_tag in roles_by_tag.items():
            for role in roles_in_tag:
                preference = talent.tag_preferences.get(tag_name, {}).get(role, 1.0)
                if preference < refusal_threshold:
                    if preference < orientation_threshold:
                        reason = f"Role involves '{tag_name}', which conflicts with their sexual orientation."
                    else:
                        reason = f"Strongly dislikes performing the '{role}' role in '{tag_name}'."
                    return AvailabilityResult(False, reason)
        return AvailabilityResult(is_available=True)

    def _check_policies(self, talent: Union[Talent, TalentDB], studio_policies: List[str]) -> AvailabilityResult:
        """Checks for global studio policy compatibility."""
        active_policies = set(studio_policies)
        policy_names = {p['id']: p['name'] for p in self.data_manager.studio_policies_data.values()}
        
        # Check if any policies the talent REQUIRES are missing
        if required_policies := talent.policy_requirements.get('requires'):
            for policy_id in required_policies:
                if policy_id not in active_policies:
                    policy_name = policy_names.get(policy_id, policy_id)
                    return AvailabilityResult(False, f"Requires the '{policy_name}' policy to be active.")
        
        # Check if any policies the talent REFUSES are active
        if refused_policies := talent.policy_requirements.get('refuses'):
            for policy_id in refused_policies:
                if policy_id in active_policies:
                    policy_name = policy_names.get(policy_id, policy_id)
                    return AvailabilityResult(False, f"Refuses to work with the '{policy_name}' policy.")

        return AvailabilityResult(is_available=True)
    
    def _check_production_budget(self, talent: Union[Talent, TalentDB], bloc_db: ShootingBlocDB) -> AvailabilityResult:
        """
        Checks if the talent will refuse to work due to low production budgets.
        A 'pickiness' score is calculated from popularity and ambition, which is
        then checked against configured budget thresholds.
        """
        # 1. Calculate Pickiness Score: More popular and ambitious talents are pickier.
        pop_scalar = self.config.pickiness_popularity_scalar
        amb_scalar = self.config.pickiness_ambition_scalar
        
        if hasattr(talent, 'popularity_scores'):
            total_popularity = sum(p.score for p in talent.popularity_scores)
        else: # Fallback for TalentDB which might not have the relationship loaded
            total_popularity = sum(talent.popularity.values())
        
        pickiness_score = (total_popularity * pop_scalar) + (talent.ambition * amb_scalar)
        
        # 2. Check Total Production Budget Refusals
        current_total_cost = bloc_db.production_cost
        
        for threshold_score, min_budget in self.config.total_budget_refusal_thresholds.items():
            if pickiness_score >= float(threshold_score):
                if current_total_cost < min_budget:
                    return AvailabilityResult(False, f"Considers the total production budget (${current_total_cost:,}) too low for their status (Requires > ${min_budget:,}).")

        # 3. Check Specific Department Budget Refusals
        current_dept_budgets = bloc_db.department_budgets or {}
        department_names = {d['id']: d['name'] for d in self.data_manager.production_departments.values()}
        
        for dept_id, thresholds in self.config.department_budget_refusal_thresholds.items():
            # If the department isn't even funded for this bloc, its budget is effectively 0.
            actual_budget = current_dept_budgets.get(dept_id, 0)
            
            for threshold_score, min_budget in thresholds.items():
                if pickiness_score >= float(threshold_score):
                    if actual_budget < min_budget:
                        dept_name = department_names.get(dept_id, dept_id.replace('_', ' ').title())
                        return AvailabilityResult(False, f"Requires a higher budget for {dept_name} (Allocated: ${actual_budget}, Requires: ${min_budget}).")

        return AvailabilityResult(is_available=True)

    def _check_contract_constraints(self, talent: Union[Talent, TalentDB], scene: Scene, roles_by_tag: Dict[str, Set[str]]) -> AvailabilityResult:
        """
        Validates if the scene adheres to the strict terms of the talent's exclusive contract.
        Contract constraints override standard willingness and preferences. If a talent
        is under contract, these rules are absolute.
        """
        contract = getattr(talent, 'contract', None)
        # If no contract, this check doesn't apply.
        if not contract:
            return AvailabilityResult(is_available=True)
            
        # 1. Check D/s Dynamic Level
        if scene.dom_sub_dynamic_level > contract.max_dynamic:
             return AvailabilityResult(False, f"Contract violation: Scene dynamic level ({scene.dom_sub_dynamic_level}) exceeds contract max ({contract.max_dynamic}).")
             
        # 2. Check Allowed Concepts and Orientations
        # A contract defines strict ALLOWED lists. If a tag in the scene maps to a
        # concept or orientation that is NOT in the allowed list, it's a violation.
        allowed_concepts = set(contract.allowed_concepts)
        allowed_orientations = set(contract.allowed_orientations)
        
        for tag_name in roles_by_tag.keys():
            tag_def = self.data_manager.tag_definitions.get(tag_name)
            if not tag_def: continue
            
            tag_concept = tag_def.get('concept')
            tag_orientation = tag_def.get('orientation')
            
            # Check Concept: If the tag has a concept, it must be in the allowed list.
            if tag_concept and tag_concept not in allowed_concepts:
                return AvailabilityResult(False, f"Contract violation: '{tag_concept}' concept is not in the contract.")
            
            # Check Orientation: If the tag has an orientation, it must be in the allowed list.
            # Tags without a specific orientation (e.g., "Solo") are implicitly allowed.
            if tag_orientation and tag_orientation not in allowed_orientations:
                 return AvailabilityResult(False, f"Contract violation: '{tag_orientation}' content is not in the contract.")
        
        # Note: Max scenes per month/week is handled by higher-level validators like
        # `BulkBookingValidator` and `ContractStatusService`, not here. This checker's
        # responsibility is validating the *content* of a single scene against the contract.
        
        return AvailabilityResult(is_available=True)  
    
    def check(
        self, 
        talent: Union[Talent, TalentDB], 
        scene: Scene, 
        vp_id: int, 
        bloc_db: Optional[ShootingBlocDB],
        bookings_before: List[Scene], 
        bookings_current: List[Scene], 
        bookings_after: List[Scene],
        estimated_fatigue_gain: int, 
        studio_policies: List[str]
    ) -> AvailabilityResult:
        """
        Runs a full check to determine if a talent is available and willing to
        take on a specific role in a scene.

        This method orchestrates a sequence of checks, returning immediately with
        a reason if any check fails. If all checks pass, it returns an available result.

        Args:
            talent: The talent being checked.
            scene: The scene dataclass containing the role.
            vp_id: The ID of the virtual performer role being checked.
            bloc_db: The DB model for the shooting bloc, if one exists. Required for budget checks.
            bookings_before: List of scenes the talent is booked for the week BEFORE the scene week.
            bookings_current: List of scenes the talent is already booked for IN the scene week.
            bookings_after: List of scenes the talent is booked for the week AFTER the scene week.
            estimated_fatigue_gain: The pre-calculated fatigue the role would cause.
            studio_policies: A list of active studio policy IDs.

        Returns:
            An `AvailabilityResult` indicating if the talent is available and a reason if not.
        """
        # The order of these checks is intentional, starting from the most basic
        # logistical constraints and moving to more nuanced content-based rules.
        
        # 1. Logistics and physical limits
        result = self._check_schedule_and_fatigue(talent, bookings_before, bookings_current, bookings_after, estimated_fatigue_gain)
        if not result.is_available: return result

        result = self._check_max_partners(talent, scene)
        if not result.is_available: return result

        # Get role context once, as it's used by multiple subsequent checks
        role_action_tags, roles_by_tag = self.get_vp_role_context(scene, vp_id)

        # 2. Content-based hard refusals
        result = self._check_hard_limits(talent, role_action_tags)
        if not result.is_available: return result
         
        result = self._check_concurrency_limits(talent, scene, vp_id, roles_by_tag)
        if not result.is_available: return result

        # 3. Contractual obligations (these are absolute and override preferences)
        result = self._check_contract_constraints(talent, scene, roles_by_tag)
        if not result.is_available: return result

        # 4. Content-based soft refusals (strong dislikes)
        result = self._check_preferences(talent, roles_by_tag)
        if not result.is_available: return result

        # 5. External factors (studio environment)
        result = self._check_policies(talent, studio_policies)
        if not result.is_available: return result

        # 6. Financial/production standards (only if part of a bloc)
        if bloc_db:
            result = self._check_production_budget(talent, bloc_db)
            if not result.is_available: return result
 
        # If all checks passed, the talent is available.
        return AvailabilityResult(is_available=True)