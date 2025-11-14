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
    A pure logic class to encapsulate the complex business rules for checking
    if a talent is available and willing to perform a specific role.
    """
    def __init__(self, data_manager: DataManager, config: HiringConfig):
        self.data_manager = data_manager
        self.config = config

    def get_vp_role_context(self, scene: Scene, vp_id: int) -> tuple[Set[str], Dict[str, Set[str]]]:
        """
        Parses the scene's expanded segments once to extract all role context for a VP.
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
                        _, role, _ = assignment.slot_id.rsplit('_', 2)
                    except ValueError:
                        role = "Performer" # Default role
                    roles_by_tag[segment.tag_name].add(role)
            
            if is_vp_in_segment:
                action_tags.add(segment.tag_name)
                
        return action_tags, dict(roles_by_tag)

    def _check_schedule_and_fatigue(self, talent: Union[Talent, TalentDB], bookings_before: List[Scene], 
                                bookings_current: List[Scene], bookings_after: List[Scene], 
                                estimated_fatigue_gain: int) -> AvailabilityResult:
        """Checks for weekly workload limits and projected fatigue, including burnout risk."""
        burnout_penalty = 0
        if bookings_before and bookings_after:
            # Talent is at risk of burnout, working three consecutive weeks.
            burnout_penalty = self.config.burnout_penalty_scenes

        # Check 1: Max Scenes Per Week
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
        projected_total_fatigue = talent.fatigue + estimated_fatigue_gain
        if projected_total_fatigue > self.config.fatigue_refusal_threshold:
            return AvailabilityResult(False, "Refuses work that would cause extreme fatigue.")

        return AvailabilityResult(is_available=True)

    def _check_max_partners(self, talent: Union[Talent, TalentDB], scene: Scene) -> AvailabilityResult:
        """Checks if the scene exceeds the talent's partner limit."""
        num_performers = len(scene.virtual_performers)
        if num_performers > 1 and (num_performers - 1) > talent.max_scene_partners:
            return AvailabilityResult(False, f"Refuses scenes with more than {talent.max_scene_partners} partners.")
        return AvailabilityResult(is_available=True)

    def _check_hard_limits(self, talent: Union[Talent, TalentDB], role_action_tags: Set[str]) -> AvailabilityResult:
        """Checks if the role involves any of the talent's hard limits."""
        for full_tag_name in role_action_tags:
            tag_def = self.data_manager.tag_definitions.get(full_tag_name)
            base_name = tag_def.get('name') if tag_def else full_tag_name
            if full_tag_name in talent.hard_limits or (base_name and base_name in talent.hard_limits):
                return AvailabilityResult(False, f"Talent has a hard limit against '{base_name}'.")
        return AvailabilityResult(is_available=True)

    def _check_concurrency_limits(self, talent: Union[Talent, TalentDB], scene: Scene, vp_id: int, roles_by_tag: Dict[str, Set[str]]) -> AvailabilityResult:
        """Checks for violations of concurrent partner limits (e.g., DP)."""
        expanded_segments = scene.get_expanded_action_segments(self.data_manager.tag_definitions)
        for segment in expanded_segments:
            if not any(a.virtual_performer_id == vp_id for a in segment.slot_assignments):
                continue
            tag_def = self.data_manager.tag_definitions.get(segment.tag_name)
            if not tag_def or not (concept := tag_def.get('concept')):
                continue
            if 'Receiver' in roles_by_tag.get(segment.tag_name, set()):
                num_givers = sum(1 for a in segment.slot_assignments if '_Giver_' in a.slot_id)
                limit = talent.concurrency_limits.get(concept, self.config.concurrency_default_limit)
                if num_givers > limit:
                    return AvailabilityResult(False, f"Concurrency limit for '{concept}' exceeded (Max: {limit}, Scene has: {num_givers}).")
        return AvailabilityResult(is_available=True)

    def _check_preferences(self, talent: Union[Talent, TalentDB], roles_by_tag: Dict[str, Set[str]]) -> AvailabilityResult:
        """Checks if the role is acceptable based on preferences and orientation."""
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

    def _check_policies_and_production(self, talent: Union[Talent, TalentDB], bloc_db: ShootingBlocDB) -> AvailabilityResult:
        """Checks for policy compatibility and production setting pickiness."""
        active_policies = set(bloc_db.on_set_policies or [])
        policy_names = {p['id']: p['name'] for p in self.data_manager.on_set_policies_data.values()}
        if required_policies := talent.policy_requirements.get('requires'):
            for policy_id in required_policies:
                if policy_id not in active_policies:
                    policy_name = policy_names.get(policy_id, policy_id)
                    return AvailabilityResult(False, f"Requires the '{policy_name}' policy to be active.")
        if refused_policies := talent.policy_requirements.get('refuses'):
            for policy_id in refused_policies:
                if policy_id in active_policies:
                    policy_name = policy_names.get(policy_id, policy_id)
                    return AvailabilityResult(False, f"Refuses to work with the '{policy_name}' policy.")
    
        pop_scalar = self.config.pickiness_popularity_scalar
        amb_scalar = self.config.pickiness_ambition_scalar
        if hasattr(talent, 'popularity_scores'):
            total_popularity = sum(p.score for p in talent.popularity_scores)
        else:
            total_popularity = sum(talent.popularity.values())
        
        pickiness_score = (total_popularity * pop_scalar) + (talent.ambition * amb_scalar)
        
        for category, tier_name in (bloc_db.production_settings or {}).items():
            tier_data = next((t for t in self.data_manager.production_settings_data.get(category, []) if t['tier_name'] == tier_name), None)
            if tier_data and tier_data.get('is_low_tier', False) and random.random() * 100 < pickiness_score:
                return AvailabilityResult(False, f"Considers the '{tier_name}' {category} setting beneath them.")
        return AvailabilityResult(is_available=True)    
    
    def check(self, talent: Union[Talent, TalentDB], scene: Scene, vp_id: int, bloc_db: Optional[ShootingBlocDB], 
          bookings_before: List[Scene], bookings_current: List[Scene], bookings_after: List[Scene], 
          estimated_fatigue_gain: int) -> AvailabilityResult:
        
        result = self._check_schedule_and_fatigue(talent, bookings_before, bookings_current, bookings_after, estimated_fatigue_gain)
        if not result.is_available: return result

        result = self._check_max_partners(talent, scene)
        if not result.is_available: return result

        role_action_tags, roles_by_tag = self.get_vp_role_context(scene, vp_id)

        result = self._check_hard_limits(talent, role_action_tags)
        if not result.is_available: return result
         
        result = self._check_concurrency_limits(talent, scene, vp_id, roles_by_tag)
        if not result.is_available: return result

        result = self._check_preferences(talent, roles_by_tag)
        if not result.is_available: return result

        if bloc_db:
            result = self._check_policies_and_production(talent, bloc_db)
            if not result.is_available: return result
 
        return AvailabilityResult(is_available=True)