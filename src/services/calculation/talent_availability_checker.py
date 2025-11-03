import random
from dataclasses import dataclass
from collections import defaultdict
from typing import Set, Dict, Optional, Union

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

    def _get_vp_role_context(self, scene: Scene, vp_id: int) -> tuple[Set[str], Dict[str, Set[str]]]:
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
        
    def check(self, talent: Union[Talent, TalentDB], scene: Scene, vp_id: int, bloc_db: Optional[ShootingBlocDB]) -> AvailabilityResult:
        # Check 1: Max Scene Partners
        num_performers = len(scene.virtual_performers)
        if num_performers > 1 and (num_performers - 1) > talent.max_scene_partners:
            return AvailabilityResult(False, f"Refuses scenes with more than {talent.max_scene_partners} partners.")

        # Check 2: Hard Limits
        role_action_tags, roles_by_tag = self._get_vp_role_context(scene, vp_id)
        for full_tag_name in role_action_tags:
            tag_def = self.data_manager.tag_definitions.get(full_tag_name)
            base_name = tag_def.get('name') if tag_def else full_tag_name
            if full_tag_name in talent.hard_limits or (base_name and base_name in talent.hard_limits):
                return AvailabilityResult(False, f"Talent has a hard limit against '{base_name}'.")
        
        # Check 3: Concurrency Limits
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

        # Check 4: Preference & Orientation Compatibility
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

        # Check 5: Policy & Production (requires bloc)
        if bloc_db:
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
            # Handle popularity from either TalentDB or Talent dataclass
            if hasattr(talent, 'popularity_scores'): # TalentDB
                total_popularity = sum(p.score for p in talent.popularity_scores)
            else: # Talent
                total_popularity = sum(talent.popularity.values())
            
            pickiness_score = (total_popularity * pop_scalar) + (talent.ambition * amb_scalar)
            
            for category, tier_name in (bloc_db.production_settings or {}).items():
                tier_data = next((t for t in self.data_manager.production_settings_data.get(category, []) if t['tier_name'] == tier_name), None)
                if tier_data and tier_data.get('is_low_tier', False) and random.random() * 100 < pickiness_score:
                    return AvailabilityResult(False, f"Considers the '{tier_name}' {category} setting beneath them.")

        return AvailabilityResult(is_available=True)