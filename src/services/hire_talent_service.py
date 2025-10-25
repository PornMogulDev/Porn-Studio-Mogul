import numpy as np
import random
from typing import Dict, Optional, List, Set
from collections import defaultdict
from sqlalchemy.orm import joinedload, selectinload

from data.game_state import Talent, Scene, ActionSegment
from services.talent_service import TalentService
from services.role_performance_service import RolePerformanceService
from data.data_manager import DataManager
from database.db_models import (
    TalentDB, SceneDB, ActionSegmentDB,
    ShootingBlocDB
)


class HireTalentService:
    def __init__(self, db_session, data_manager: DataManager, talent_service: TalentService, role_perf_service: RolePerformanceService):
        self.session = db_session
        self.data_manager = data_manager
        self.talent_service = talent_service
        self.role_performance_service = role_perf_service

    def _get_roles_by_tag_for_vp(self, scene: Scene, vp_id: int) -> Dict[str, Set[str]]:
        """Helper to get a map of tags to the set of roles a VP performs in them."""
        roles_by_tag = defaultdict(set)
        expanded_segments = scene.get_expanded_action_segments(self.data_manager.tag_definitions)
        for segment in expanded_segments:
            for assignment in segment.slot_assignments:
                if assignment.virtual_performer_id == vp_id:
                    try:
                        _, role, _ = assignment.slot_id.rsplit('_', 2)
                    except ValueError:
                        role = "Performer" # Default role if parsing fails
                    roles_by_tag[segment.tag_name].add(role)
        return dict(roles_by_tag)

    def _get_action_tags_for_role(self, scene: Scene, vp_id: int) -> List[str]:
        """Helper to find all action tags a specific virtual performer is involved in for a scene."""
        role_tags = set()
        expanded_segments = scene.get_expanded_action_segments(self.data_manager.tag_definitions)
        for segment in expanded_segments:
            for assignment in segment.slot_assignments:
                if assignment.virtual_performer_id == vp_id:
                    role_tags.add(segment.tag_name)
                    break
        return list(role_tags)

    def _get_role_tags_for_display(self, scene: Scene, vp_id: int) -> List[str]:
        """Helper to get a formatted list of tags and roles for UI display."""
        role_tags_map = defaultdict(set)
        expanded_segments = scene.get_expanded_action_segments(self.data_manager.tag_definitions)
        for segment in expanded_segments:
            for assignment in segment.slot_assignments:
                if assignment.virtual_performer_id == vp_id:
                    try: _, role, _ = assignment.slot_id.rsplit('_', 2)
                    except ValueError: role_tags_map[segment.tag_name].add("Performer")
                    else: role_tags_map[segment.tag_name].add(role)
        
        tags_with_roles = [f"{tag_name} ({', '.join(sorted(list(roles)))})" for tag_name, roles in sorted(role_tags_map.items())]
        return tags_with_roles

    def get_eligible_talent_for_role(self, scene_id: int, vp_id: int) -> List[Talent]:
        """
        Finds all available talents who are eligible and willing to take on a specific
        uncast role in a given scene.
        """
        # --- Step A: Gather Context ---
        scene_db = self.session.query(SceneDB).options(
            selectinload(SceneDB.virtual_performers),
            selectinload(SceneDB.cast),
            selectinload(SceneDB.action_segments).selectinload(ActionSegmentDB.slot_assignments)
        ).get(scene_id)
        if not scene_db: return []
        scene = scene_db.to_dataclass(Scene)

        vp = next((v for v in scene.virtual_performers if v.id == vp_id), None)
        if not vp: return []

        bloc_db = self.session.query(ShootingBlocDB).get(scene_db.bloc_id) if scene_db.bloc_id else None
        
        # --- Step B: Initial Database Query ---
        query = self.session.query(TalentDB)
        query = query.filter(TalentDB.gender == vp.gender)
        if vp.ethnicity != "Any":
            query = query.filter(TalentDB.ethnicity == vp.ethnicity)
        if cast_talent_ids := {c.talent_id for c in scene_db.cast}:
            query = query.filter(TalentDB.id.notin_(cast_talent_ids))

        # --- Step C: In-Memory Python Filtering ---
        potential_candidates_db = query.all()
        eligible_talents = []

        for talent_db in potential_candidates_db:
            talent = talent_db.to_dataclass(Talent)
            
            # Use the detailed check from find_available_roles_for_talent
            # We don't need the full role_info dict here, just the availability
            is_available, _ = self._check_talent_availability_for_role(talent, scene, vp.id, scene_db, bloc_db)

            if is_available:
                eligible_talents.append(talent)
            
        return sorted(eligible_talents, key=lambda t: t.alias)

    def _check_talent_availability_for_role(self, talent: Talent, scene: Scene, vp_id: int, scene_db: SceneDB, bloc_db: Optional[ShootingBlocDB]) -> tuple[bool, Optional[str]]:
        """
        A centralized checker for a talent's availability for a specific role.
        Returns (is_available, refusal_reason).
        """
        # Check 1: Max Scene Partners
        num_performers = len(scene.virtual_performers)
        if num_performers > 1 and (num_performers - 1) > talent.max_scene_partners:
            return False, f"Refuses scenes with more than {talent.max_scene_partners} partners."

        # Check 2: Hard Limits
        role_action_tags = self._get_action_tags_for_role(scene, vp_id)
        for full_tag_name in role_action_tags:
            tag_def = self.data_manager.tag_definitions.get(full_tag_name)
            # Should always exist, but guard just in case
            base_name = tag_def.get('name') if tag_def else full_tag_name

            if full_tag_name in talent.hard_limits or (base_name and base_name in talent.hard_limits):
                return False, f"Talent has a hard limit against '{base_name}'."
        
        # Check 3: Concurrency Limits
        expanded_segments = scene.get_expanded_action_segments(self.data_manager.tag_definitions)
        roles_by_tag = self._get_roles_by_tag_for_vp(scene, vp_id)
        
        for segment in expanded_segments:
            # Check if the current vp is even in this segment
            if not any(a.virtual_performer_id == vp_id for a in segment.slot_assignments):
                continue
            
            tag_def = self.data_manager.tag_definitions.get(segment.tag_name)
            if not tag_def or not (concept := tag_def.get('concept')):
                continue

            # This check is primarily for receptive roles (Receiver)
            if 'Receiver' in roles_by_tag.get(segment.tag_name, set()):
                num_givers = sum(1 for a in segment.slot_assignments if '_Giver_' in a.slot_id)
                limit = talent.concurrency_limits.get(
                    concept, self.data_manager.game_config.get("hiring_concurrency_default_limit", 99)
                )
                if num_givers > limit:
                    return False, f"Concurrency limit for '{concept}' exceeded (Max: {limit}, Scene has: {num_givers})."

        # Check 4: Preference & Orientation Compatibility
        refusal_threshold = self.data_manager.game_config.get("talent_refusal_threshold", 0.2)
        orientation_threshold = self.data_manager.game_config.get("talent_orientation_refusal_threshold", 0.1)
        for tag_name, roles_in_tag in roles_by_tag.items():
            for role in roles_in_tag:
                preference = talent.tag_preferences.get(tag_name, {}).get(role, 1.0)
                if preference < refusal_threshold:
                    if preference < orientation_threshold: # Extremely low score implies orientation conflict
                        reason = f"Role involves '{tag_name}', which conflicts with their sexual orientation."
                    else:
                        reason = f"Strongly dislikes performing the '{role}' role in '{tag_name}'."
                    return False, reason

        # Check 5: Policy & Production (requires bloc)
        if bloc_db:
            active_policies = set(bloc_db.on_set_policies or [])
            policy_names = {p['id']: p['name'] for p in self.data_manager.on_set_policies_data.values()}

            if required_policies := talent.policy_requirements.get('requires'):
                for policy_id in required_policies:
                    if policy_id not in active_policies:
                        policy_name = policy_names.get(policy_id, policy_id)
                        return False, f"Requires the '{policy_name}' policy to be active."

            if refused_policies := talent.policy_requirements.get('refuses'):
                for policy_id in refused_policies:
                    if policy_id in active_policies:
                        policy_name = policy_names.get(policy_id, policy_id)
                        return False, f"Refuses to work with the '{policy_name}' policy."
        
            pop_scalar = self.data_manager.game_config.get("pickiness_popularity_scalar", 0.4)
            amb_scalar = self.data_manager.game_config.get("pickiness_ambition_scalar", 2.5)
            total_popularity = sum(talent.popularity.values())
            pickiness_score = (total_popularity * pop_scalar) + (talent.ambition * amb_scalar)
            
            for category, tier_name in (bloc_db.production_settings or {}).items():
                tier_data = next((t for t in self.data_manager.production_settings_data.get(category, []) if t['tier_name'] == tier_name), None)
                if tier_data and tier_data.get('is_low_tier', False) and random.random() * 100 < pickiness_score:
                    return False, f"Considers the '{tier_name}' {category} setting beneath them."

        return True, None # If all checks pass

    def find_available_roles_for_talent(self, talent_id: int) -> List[Dict]:
        """
        Finds all uncast roles in 'casting' scenes that a given talent is eligible for,
        and calculates the hiring cost for each. Includes availability and refusal reasons.
        """
        talent = self.talent_service.get_talent_by_id(talent_id)
        if not talent: return []

        available_roles = []
        scenes_in_casting = self.session.query(SceneDB)\
            .options(selectinload(SceneDB.virtual_performers), selectinload(SceneDB.cast),
                    selectinload(SceneDB.action_segments).selectinload(ActionSegmentDB.slot_assignments))\
            .filter(SceneDB.status == 'casting').all()
        
        # Pre-fetch all shooting blocs for these scenes to avoid N+1 queries
        bloc_ids = {s.bloc_id for s in scenes_in_casting if s.bloc_id}
        blocs_by_id = {}
        if bloc_ids:
            blocs_db = self.session.query(ShootingBlocDB).filter(ShootingBlocDB.id.in_(bloc_ids)).all()
            blocs_by_id = {b.id: b for b in blocs_db}
        
        for scene_db in scenes_in_casting:
            scene = scene_db.to_dataclass(Scene); cast_talent_ids = {c.talent_id for c in scene_db.cast}
            if talent.id in cast_talent_ids: continue

            all_vp_ids = {vp.id for vp in scene_db.virtual_performers}; cast_vp_ids = {c.virtual_performer_id for c in scene_db.cast}
            uncast_vp_ids = all_vp_ids - cast_vp_ids
            
            for vp_db in scene_db.virtual_performers:
                if vp_db.id not in uncast_vp_ids: continue
                if not (vp_db.gender == talent.gender and (vp_db.ethnicity == "Any" or vp_db.ethnicity == talent.ethnicity)): continue
                
                bloc_db = blocs_by_id.get(scene.bloc_id) if scene.bloc_id else None
                is_available, refusal_reason = self._check_talent_availability_for_role(
                    talent, scene, vp_db.id, scene_db, bloc_db
                )

                role_info = {
                    'scene_id': scene_db.id, 'scene_title': scene_db.title, 'virtual_performer_id': vp_db.id,
                    'vp_name': vp_db.name, 'cost': self.calculate_talent_demand(talent.id, scene_db.id, vp_db.id),
                    'tags': self._get_role_tags_for_display(scene, vp_db.id),
                    'is_available': is_available, 'refusal_reason': refusal_reason
                }
                
                available_roles.append(role_info)
        return available_roles

    def calculate_talent_demand(self, talent_id, scene_id, vp_id: int) -> int:
        talent = self.talent_service.get_talent_by_id(talent_id)
        # We need the Scene dataclass for its complex logic methods
        scene_db = self.session.query(SceneDB).options(
            joinedload(SceneDB.virtual_performers),
            joinedload(SceneDB.action_segments).joinedload(ActionSegmentDB.slot_assignments)
        ).get(scene_id)
        
        if not talent or not scene_db: return 0
        scene = scene_db.to_dataclass(Scene)

        base_demand = self.data_manager.game_config.get("base_talent_demand", 400)
        performance_multiplier = 1 + (talent.performance / self.data_manager.game_config.get("hiring_demand_perf_divisor", 200))
        median_ambition = self.data_manager.game_config.get("median_ambition", 5.5)
        ambition_demand_divisor = self.data_manager.game_config.get("ambition_demand_divisor", 10.0)
        ambition_multiplier = 1.0 + ((talent.ambition - median_ambition) / ambition_demand_divisor)
        
        overall_popularity = sum(talent.popularity.values())

        popularity_demand_scalar = self.data_manager.game_config.get("popularity_demand_scalar", 0.05)
        popularity_multiplier = 1.0 + (overall_popularity * popularity_demand_scalar)
        
        role_multiplier = 1.0; max_demand_mod = 1.0
        action_segments_for_calc = scene.get_expanded_action_segments(self.data_manager.tag_definitions)
        for segment in action_segments_for_calc:
            slots = scene._get_slots_for_segment(segment, self.data_manager.tag_definitions)
            for assignment in segment.slot_assignments:
                if assignment.virtual_performer_id == vp_id:
                    try: _ , role, _ = assignment.slot_id.rsplit('_', 2)
                    except ValueError: continue
                    slot_def = next((s for s in slots if s['role'] == role), None)
                    if not slot_def: continue
                    final_mod = self.role_performance_service.get_final_modifier('demand_modifier', slot_def, segment, role)
                    max_demand_mod = max(max_demand_mod, final_mod)
        role_multiplier = max_demand_mod
        
        roles_by_tag = self._get_roles_by_tag_for_vp(scene, vp_id)
        preference_scores = []
        if roles_by_tag:
            for tag_name, roles in roles_by_tag.items():
                for role in roles:
                    score = talent.tag_preferences.get(tag_name, {}).get(role, 1.0)
                    preference_scores.append(score)
        
        preference_multiplier = np.mean(preference_scores) if preference_scores else 1.0
        
        final_demand = base_demand * performance_multiplier * ambition_multiplier * role_multiplier * popularity_multiplier
        
        # A preference > 1 reduces cost; a preference < 1 increases it.
        if preference_multiplier > 0:
            final_demand /= preference_multiplier

        return max(self.data_manager.game_config.get("minimum_talent_demand", 100), int(final_demand))
    
    def get_role_details_for_ui(self, scene_id: int, vp_id: int) -> Dict:
        """
        Fetches a comprehensive dictionary of a specific role's details for UI display.
        """
        scene_db = self.session.query(SceneDB).options(
            selectinload(SceneDB.virtual_performers),
            selectinload(SceneDB.action_segments).selectinload(ActionSegmentDB.slot_assignments)
        ).get(scene_id)
        if not scene_db:
            return {}
        
        scene = scene_db.to_dataclass(Scene)
        vp = next((v for v in scene.virtual_performers if v.id == vp_id), None)
        if not vp:
            return {}

        physical_tags = [tag for tag, vps in scene.assigned_tags.items() if vp_id in vps]

        details = {
            'gender': vp.gender,
            'ethnicity': vp.ethnicity,
            'is_protagonist': vp_id in scene.protagonist_vp_ids,
            'disposition': vp.disposition,
            'physical_tags': sorted(physical_tags),
            'action_roles': self._get_role_tags_for_display(scene, vp_id)
        }
        return details