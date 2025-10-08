import numpy as np
import random
from typing import Dict, Optional, List, Set
from collections import defaultdict
from sqlalchemy.orm import joinedload, selectinload

from game_state import Talent, Scene, ActionSegment
from services.market_service import MarketService
from data_manager import DataManager
from database.db_models import TalentDB, SceneDB, VirtualPerformerDB, ActionSegmentDB, TalentChemistryDB, ShootingBlocDB

class TalentService:
    def __init__(self, db_session, data_manager: DataManager, market_service: MarketService):
        self.session = db_session
        self.data_manager = data_manager
        self.market_service = market_service
    def get_talent_by_id(self, talent_id: int) -> Optional[Talent]:
        """Fetches a single talent from the DB and converts it to a dataclass."""
        talent_db = self.session.query(TalentDB).get(talent_id)
        return talent_db.to_dataclass(Talent) if talent_db else None

    def get_talent_chemistry(self, talent_id: int) -> List[Dict]:
        """
        Fetches all chemistry relationships for a given talent for UI display.
        Returns a list of dictionaries with the other talent's ID, alias, and the score.
        """
        results = []
        
        # Query where the talent is talent_a
        query_a = self.session.query(TalentChemistryDB, TalentDB.id, TalentDB.alias)\
            .join(TalentDB, TalentChemistryDB.talent_b_id == TalentDB.id)\
            .filter(TalentChemistryDB.talent_a_id == talent_id)
            
        for chem, other_id, other_alias in query_a.all():
            results.append({
                "other_talent_id": other_id,
                "other_talent_alias": other_alias,
                "score": chem.chemistry_score
            })

        # Query where the talent is talent_b
        query_b = self.session.query(TalentChemistryDB, TalentDB.id, TalentDB.alias)\
            .join(TalentDB, TalentChemistryDB.talent_a_id == TalentDB.id)\
            .filter(TalentChemistryDB.talent_b_id == talent_id)

        for chem, other_id, other_alias in query_b.all():
            results.append({
                "other_talent_id": other_id,
                "other_talent_alias": other_alias,
                "score": chem.chemistry_score
            })
            
        return sorted(results, key=lambda x: x['other_talent_alias'])

    def get_filtered_talents(self, filters: dict) -> List[Talent]:
        """
        Builds and executes a dynamic query to fetch talents from the DB
        based on a dictionary of filter criteria.
        """
        query = self.session.query(TalentDB)

        # Text filter
        if text := filters.get('text', '').strip():
            query = query.filter(TalentDB.alias.ilike(f'%{text}%'))
        
        # Age
        query = query.filter(TalentDB.age >= filters.get('age_min', 18))
        query = query.filter(TalentDB.age <= filters.get('age_max', 99))
        
        # Gender
        if gender := filters.get('gender'):
            if gender != "Any":
                query = query.filter(TalentDB.gender == gender)
        
        # Ethnicity
        if ethnicities := filters.get('ethnicities'):
            query = query.filter(TalentDB.ethnicity.in_(ethnicities))
        
        # Boob Cups
        if boob_cups := filters.get('boob_cups'):
            query = query.filter(TalentDB.boob_cup.in_(boob_cups))
            
        # Dick Size
        min_d, max_d = filters.get('dick_size_min', 0), filters.get('dick_size_max', 20)
        if min_d > 0 or max_d < 20:
            query = query.filter(TalentDB.dick_size != None)
            query = query.filter(TalentDB.dick_size.between(min_d, max_d))
            
        # Skills & Attributes
        query = query.filter(TalentDB.performance.between(filters.get('performance_min', 0.0), filters.get('performance_max', 100.0)))
        query = query.filter(TalentDB.acting.between(filters.get('acting_min', 0.0), filters.get('acting_max', 100.0)))
        query = query.filter(TalentDB.stamina.between(filters.get('stamina_min', 0.0), filters.get('stamina_max', 100.0)))
        query = query.filter(TalentDB.ambition.between(filters.get('ambition_min', 1), filters.get('ambition_max', 10)))

        results = query.order_by(TalentDB.alias).all()
        return [t.to_dataclass(Talent) for t in results]

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
        active_policies = set(bloc_db.on_set_policies or []) if bloc_db else set()
        
        role_action_tags = self._get_action_tags_for_role(scene, vp_id)
        
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
            
            # Hard Limit Check
            if any(tag in talent.hard_limits for tag in role_action_tags):
                continue
                
            # Policy Compatibility Check
            is_incompatible = False
            if required := talent.policy_requirements.get('requires'):
                if not set(required).issubset(active_policies): is_incompatible = True
            if not is_incompatible and (refused := talent.policy_requirements.get('refuses')):
                if any(policy in active_policies for policy in refused): is_incompatible = True
            if is_incompatible: continue
                
            # Preference & Orientation Compatibility Check
            refusal_threshold = self.data_manager.game_config.get("talent_refusal_threshold", 0.2)
            roles_by_tag = self._get_roles_by_tag_for_vp(scene, vp.id)
            is_refused = False
            for tag_name, roles_in_tag in roles_by_tag.items():
                for role in roles_in_tag:
                    if talent.tag_preferences.get(tag_name, {}).get(role, 1.0) < refusal_threshold:
                        is_refused = True; break
                if is_refused: break
            if is_refused: continue

            # Production Snobbery Check
            if bloc_db:
                pop_scalar = self.data_manager.game_config.get("pickiness_popularity_scalar", 0.4)
                amb_scalar = self.data_manager.game_config.get("pickiness_ambition_scalar", 2.5)
                pickiness_score = (sum(talent.popularity.values()) * pop_scalar) + (talent.ambition * amb_scalar)
                
                is_snob = False
                for category, tier_name in (bloc_db.production_settings or {}).items():
                    tier_data = next((t for t in self.data_manager.production_settings_data.get(category, []) if t['tier_name'] == tier_name), None)
                    if tier_data and tier_data.get('is_low_tier', False) and random.random() * 100 < pickiness_score:
                        is_snob = True; break
                if is_snob: continue

            eligible_talents.append(talent)
            
        return sorted(eligible_talents, key=lambda t: t.alias)

    def find_available_roles_for_talent(self, talent_id: int) -> List[Dict]:
        """
        Finds all uncast roles in 'casting' scenes that a given talent is eligible for,
        and calculates the hiring cost for each. Includes availability and refusal reasons.
        """
        talent = self.get_talent_by_id(talent_id)
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

                role_info = {
                    'scene_id': scene_db.id, 'scene_title': scene_db.title, 'virtual_performer_id': vp_db.id,
                    'vp_name': vp_db.name, 'cost': self.calculate_talent_demand(talent.id, scene_db.id, vp_db.id),
                    'tags': self._get_role_tags_for_display(scene, vp_db.id),
                    'is_available': True, 'refusal_reason': None
                }
                
                # Check 1: Preference & Orientation Compatibility
                refusal_threshold = self.data_manager.game_config.get("talent_refusal_threshold", 0.2)
                roles_by_tag = self._get_roles_by_tag_for_vp(scene, vp_db.id)
                is_refused = False
                for tag_name, roles_in_tag in roles_by_tag.items():
                    for role in roles_in_tag:
                        preference = talent.tag_preferences.get(tag_name, {}).get(role, 1.0)
                        if preference < refusal_threshold:
                            role_info['is_available'] = False
                            if preference < 0.1: # Extremely low score implies orientation conflict
                                reason = f"Role involves '{tag_name}', which conflicts with their sexual orientation."
                            else:
                                reason = f"Strongly dislikes performing the '{role}' role in '{tag_name}'."
                            role_info['refusal_reason'] = reason
                            is_refused = True
                            break
                    if is_refused: break
                
                if is_refused:
                    available_roles.append(role_info)
                    continue

                # Check 2: Hard Limits
                role_action_tags = self._get_action_tags_for_role(scene, vp_db.id)
                for tag_name in role_action_tags:
                    if tag_name in talent.hard_limits:
                        role_info['is_available'] = False; role_info['refusal_reason'] = f"Talent has a hard limit against '{tag_name}'."
                        available_roles.append(role_info); break
                if not role_info['is_available']: continue

                # Check 3: Policy Compatibility & Production Snobbery (bloc-dependent checks)
                if scene.bloc_id and (bloc_db := blocs_by_id.get(scene.bloc_id)):
                    active_policies = set(bloc_db.on_set_policies or [])
                    policy_names = {p['id']: p['name'] for p in self.data_manager.on_set_policies_data.values()}

                    # Check for required policies
                    if required_policies := talent.policy_requirements.get('requires'):
                        for policy_id in required_policies:
                            if policy_id not in active_policies:
                                policy_name = policy_names.get(policy_id, policy_id)
                                role_info['is_available'] = False
                                role_info['refusal_reason'] = f"Requires the '{policy_name}' policy to be active."
                                available_roles.append(role_info); break
                    if not role_info['is_available']: continue

                    # Check for refused policies
                    if refused_policies := talent.policy_requirements.get('refuses'):
                        for policy_id in refused_policies:
                            if policy_id in active_policies:
                                policy_name = policy_names.get(policy_id, policy_id)
                                role_info['is_available'] = False
                                role_info['refusal_reason'] = f"Refuses to work with the '{policy_name}' policy."
                                available_roles.append(role_info); break
                    if not role_info['is_available']: continue
                
                    # Check for "Production Snobbery"
                    pop_scalar = self.data_manager.game_config.get("pickiness_popularity_scalar", 0.4)
                    amb_scalar = self.data_manager.game_config.get("pickiness_ambition_scalar", 2.5)
                    total_popularity = sum(talent.popularity.values())
                    pickiness_score = (total_popularity * pop_scalar) + (talent.ambition * amb_scalar)
                    
                    for category, tier_name in (bloc_db.production_settings or {}).items():
                        tier_data = next((t for t in self.data_manager.production_settings_data.get(category, []) if t['tier_name'] == tier_name), None)
                        if tier_data and tier_data.get('is_low_tier', False) and random.random() * 100 < pickiness_score:
                            role_info['is_available'] = False
                            role_info['refusal_reason'] = f"Considers the '{tier_name}' {category} setting beneath them."
                            available_roles.append(role_info); break
                    if not role_info['is_available']: continue

                available_roles.append(role_info)
        return available_roles

    def recalculate_talent_age_affinities(self, talent: Talent):
        gender_data = self.data_manager.affinity_data.get(talent.gender)
        new_affinities = {}
        if not gender_data: 
            return new_affinities
        
        raw_scores = {}
        for tag, data in gender_data.items():
            age_points, values = data.get("age_points", []), data.get("values", [])
            if age_points and values: 
                raw_scores[tag] = np.interp(talent.age, age_points, values)
        
        total_raw_score = sum(raw_scores.values())
        if total_raw_score == 0:
            for tag in gender_data: 
                new_affinities[tag] = 0
            return new_affinities
            
        for tag, raw_score in raw_scores.items():
            new_affinities[tag] = int(round((raw_score / total_raw_score) * 100))
            
        return new_affinities

    def calculate_skill_gain(self, talent: Talent, scene_runtime_minutes: int) -> tuple[float, float, float]:
        base_rate = self.data_manager.game_config.get("skill_gain_base_rate_per_minute", 0.02)
        ambition_scalar = self.data_manager.game_config.get("skill_gain_ambition_scalar", 0.015)
        cap = self.data_manager.game_config.get("skill_gain_diminishing_returns_cap", 100.0)
        median_ambition = self.data_manager.game_config.get("median_ambition", 5.5)
        ambition_modifier = 1.0 + ((talent.ambition - median_ambition) * ambition_scalar)
        base_gain = scene_runtime_minutes * base_rate * ambition_modifier
        
        def get_final_gain(current_skill_level: float) -> float:
            if current_skill_level >= cap: return 0.0
            return base_gain * (1.0 - (current_skill_level / cap))
            
        return get_final_gain(talent.performance), get_final_gain(talent.acting), get_final_gain(talent.stamina)

    def get_talent_final_modifier(self, base_modifier_key: str, slot_def: dict, segment: ActionSegment, role: str) -> float:
        base_mod = slot_def.get(base_modifier_key, 1.0)
        scaling_mod_other = slot_def.get(f"{base_modifier_key}_scaling_per_other", 0.0)
        scaling_mod_peer = slot_def.get(f"{base_modifier_key}_scaling_per_peer", 0.0)
        
        other_role = 'Giver' if role == 'Receiver' else 'Receiver'
        num_others = segment.parameters.get(other_role, 0)
        
        bonus_mod = 0.0
        if num_others > 1 and scaling_mod_other > 0: bonus_mod += (num_others - 1) * scaling_mod_other

        num_peers = segment.parameters.get(role, 0)
        if num_peers > 1 and scaling_mod_peer > 0: bonus_mod += (num_peers - 1) * scaling_mod_peer
            
        return base_mod + bonus_mod

    def calculate_talent_demand(self, talent_id, scene_id, vp_id: int) -> int:
        talent = self.get_talent_by_id(talent_id)
        # We need the Scene dataclass for its complex logic methods
        scene_db = self.session.query(SceneDB).options(
            joinedload(SceneDB.virtual_performers),
            joinedload(SceneDB.action_segments).joinedload(ActionSegmentDB.slot_assignments)
        ).get(scene_id)
        
        if not talent or not scene_db: return 0
        scene = scene_db.to_dataclass(Scene)

        base_demand = self.data_manager.game_config.get("base_talent_demand", 450)
        performance_multiplier = 1 + (talent.performance / 200.0)
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
                    final_mod = self.get_talent_final_modifier('demand_modifier', slot_def, segment, role)
                    max_demand_mod = max(max_demand_mod, final_mod)
        role_multiplier = max_demand_mod
        
        # --- NEW: Preference Multiplier ---
        roles_by_tag = self._get_roles_by_tag_for_vp(scene, vp_id)
        preference_scores = []
        if roles_by_tag:
            for tag_name, roles in roles_by_tag.items():
                for role in roles:
                    score = talent.tag_preferences.get(tag_name, {}).get(role, 1.0)
                    preference_scores.append(score)
        
        preference_multiplier = np.mean(preference_scores) if preference_scores else 1.0
        
        # --- Final Calculation ---
        final_demand = base_demand * performance_multiplier * ambition_multiplier * role_multiplier * popularity_multiplier
        
        # A preference > 1 reduces cost; a preference < 1 increases it.
        if preference_multiplier > 0:
            final_demand /= preference_multiplier

        return max(self.data_manager.game_config.get("minimum_talent_demand", 100), int(final_demand))

    def update_popularity_from_scene(self, scene_id: int):
        scene_db = self.session.query(SceneDB).get(scene_id)
        if not scene_db: return
        scene = scene_db.to_dataclass(Scene) # Use dataclass for easy data access
        
        gain_rate = self.data_manager.game_config.get("popularity_gain_base_rate", 2.0)
        max_pop = self.data_manager.game_config.get("max_popularity_per_group", 100.0)
        
        cast_talent_ids = list(scene.final_cast.values())
        if not cast_talent_ids: return
        
        cast_talents_db = self.session.query(TalentDB).filter(TalentDB.id.in_(cast_talent_ids)).all()
        if not cast_talents_db: return

        direct_gains = defaultdict(lambda: defaultdict(float))
        for group_name, interest_score in scene.viewer_group_interest.items():
            if interest_score > 0:
                gain = interest_score * gain_rate
                for talent_db in cast_talents_db: direct_gains[talent_db.id][group_name] += gain
        
        final_gains = defaultdict(lambda: defaultdict(float), {tid: gains.copy() for tid, gains in direct_gains.items()})
        resolved_market_groups = {g['name']: self.market_service.get_resolved_group_data(g['name']) for g in self.data_manager.market_data.get('viewer_groups', [])}
        
        for talent_id, gains_by_group in direct_gains.items():
            for source_group_name, gain_amount in gains_by_group.items():
                source_group_data = resolved_market_groups.get(source_group_name)
                if source_group_data:
                    spillover_rules = source_group_data.get('popularity_spillover', {})
                    for target_group_name, spill_rate in spillover_rules.items():
                        spillover_amount = gain_amount * spill_rate
                        final_gains[talent_id][target_group_name] += spillover_amount

        for talent_db in cast_talents_db:
            gains_by_group = final_gains.get(talent_db.id, {})
            for group_name, gain_amount in gains_by_group.items():
                # Find the existing popularity entry or create a new one
                pop_entry = self.session.query(TalentPopularityDB).filter_by(
                    talent_id=talent_db.id,
                    market_group_name=group_name
                ).one_or_none()

                if not pop_entry:
                    pop_entry = TalentPopularityDB(talent_id=talent_db.id, market_group_name=group_name, score=0.0)
                    self.session.add(pop_entry)
                
                pop_entry.score = min(max_pop, pop_entry.score + gain_amount)