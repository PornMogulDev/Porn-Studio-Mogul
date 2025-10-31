import logging
import numpy as np
import random
from collections import defaultdict
from itertools import combinations, permutations
from typing import Dict, List, Optional, Set, Tuple
from sqlalchemy.orm.attributes import flag_modified
from database.db_models import ShootingBlocDB

from data.game_state import Scene, Talent
from data.data_manager import DataManager
from services.talent_service import TalentService
from services.role_performance_service import RolePerformanceService
from services.market_service import MarketService
from database.db_models import ( SceneDB, MarketGroupStateDB, TalentDB, GameInfoDB, ShootingBlocDB,
                                ScenePerformerContributionDB, SceneCastDB, TalentChemistryDB )

logger = logging.getLogger(__name__)

class SceneCalculationService:
    def __init__(self, db_session, data_manager: DataManager, talent_service: TalentService, market_service: MarketService):
        self.session = db_session
        self.data_manager = data_manager
        self.talent_service = talent_service
        self.market_service = market_service
    
    def calculate_shoot_results(self, scene_db: SceneDB, shoot_modifiers: Dict):
        total_salary_cost = sum(c.salary for c in scene_db.cast)
        
        if total_salary_cost > 0:
            money_info = self.session.query(GameInfoDB).filter_by(key='money').one()
            current_money = int(float(money_info.value))
            new_money = current_money - total_salary_cost
            money_info.value = str(new_money)

        scene = scene_db.to_dataclass(Scene) 
        cast_talents = {talent_id: self.talent_service.get_talent_by_id(talent_id) for talent_id in scene.final_cast.values()}
        
        self.talent_service.discover_and_create_chemistry(scene, cast_talents)
        talent_stamina_cost = defaultdict(float); action_segments_for_calc = scene.get_expanded_action_segments(self.data_manager.tag_definitions)
    
        for segment in action_segments_for_calc:
            segment_runtime = scene.total_runtime_minutes * (segment.runtime_percentage / 100.0); slots = scene._get_slots_for_segment(segment, self.data_manager.tag_definitions)
            for assignment in segment.slot_assignments:
                talent_id = scene.final_cast.get(str(assignment.virtual_performer_id))
                if not talent_id: continue
                try: _, role, _ = assignment.slot_id.rsplit('_', 2) 
                except ValueError: continue
                slot_def = next((s for s in slots if s['role'] == role), None)
                if not slot_def: continue
                final_mod = RolePerformanceService.get_final_modifier('stamina_modifier', slot_def, segment, role); cost = segment_runtime * final_mod
                talent_stamina_cost[talent_id] += cost
        
        scene.performer_stamina_costs = {str(tid): cost for tid, cost in talent_stamina_cost.items()}
        stamina_multiplier = self.data_manager.game_config.get("stamina_to_pool_multiplier", 5); max_skill = self.data_manager.game_config.get("maximum_skill_level", 100.0)
        
        talent_ids_to_update = list(talent_stamina_cost.keys())
        talents_db = self.session.query(TalentDB).filter(TalentDB.id.in_(talent_ids_to_update)).all()
        # Map talent IDs to their virtual performer to get disposition
        vp_id_to_talent_id = {int(k): v for k, v in scene.final_cast.items()}
        talent_id_to_vp = {v: k for k, v in vp_id_to_talent_id.items()}
        vp_map = {vp.id: vp for vp in scene.virtual_performers}

        for talent_db in talents_db:
            total_cost = talent_stamina_cost.get(talent_db.id, 0.0)
            max_stamina = talent_db.stamina * stamina_multiplier
            if total_cost > max_stamina:
                overdraw_ratio = (total_cost - max_stamina) / max_stamina; fatigue_gain = min(100, int(overdraw_ratio * 100))
                talent_db.fatigue = min(100, talent_db.fatigue + fatigue_gain)
                duration_weeks = self.data_manager.game_config.get("base_fatigue_weeks", 2)
                
                week_info = self.session.query(GameInfoDB).filter_by(key='week').one()
                year_info = self.session.query(GameInfoDB).filter_by(key='year').one()
                current_week, current_year = int(week_info.value), int(year_info.value)
                
                end_week, end_year = current_week + duration_weeks, current_year
                if end_week > 52: end_week -= 52; end_year += 1
                talent_db.fatigue_end_week, talent_db.fatigue_end_year = end_week, end_year
            
            talent_obj = talent_db.to_dataclass(Talent)
            # 1. Calculate all gains using TalentService
            p_gain, a_gain, s_gain = self.talent_service.calculate_skill_gain(talent_obj, scene.total_runtime_minutes)
            dom_gain, sub_gain = 0.0, 0.0 # Default to 0
            exp_gain = self.talent_service.calculate_experience_gain(talent_obj, scene.total_runtime_minutes) # New line

            # D/S Skill Progression
            vp_id = talent_id_to_vp.get(talent_db.id)
            if vp_id and (vp := vp_map.get(vp_id)):
                dom_gain, sub_gain = self.talent_service.calculate_ds_skill_gain(talent_obj, scene, vp.disposition)
            
            # 2. Apply all gains to the DB object
            talent_db.performance = min(max_skill, talent_db.performance + p_gain)
            talent_db.acting = min(max_skill, talent_db.acting + a_gain)
            talent_db.stamina = min(max_skill, talent_db.stamina + s_gain)
            talent_db.dom_skill = min(max_skill, talent_db.dom_skill + dom_gain)
            talent_db.sub_skill = min(max_skill, talent_db.sub_skill + sub_gain)
            # Apply the experience gain using the same pattern
            talent_db.experience = min(100.0, talent_db.experience + exp_gain) # New line
            
        composition_tags_with_scores = self._analyze_cast_composition(scene)
        scene.auto_tags = sorted(list(composition_tags_with_scores.keys()))
        
        performer_mods = shoot_modifiers.get('performer_mods', {})
        quality_mods = shoot_modifiers.get('quality_mods', {})
        new_contributions, scene_tag_qualities = self.calculate_scene_quality(scene, performer_mods, quality_mods, stamina_multiplier)
        
        # Clear any old contributions before adding new ones
        scene_db.performer_contributions_rel.clear() 
        for contrib_data in new_contributions:
            contrib_db = ScenePerformerContributionDB(
                scene_id=scene_db.id,
                talent_id=contrib_data['talent_id'],
                contribution_key=contrib_data['key'],
                quality_score=contrib_data['score']
            )
            # Add to the session through the relationship
            scene_db.performer_contributions_rel.append(contrib_db)
        
        # Update DB object and explicitly flag JSON fields as modified
        scene_db.performer_stamina_costs = scene.performer_stamina_costs.copy()
        scene_db.auto_tags = scene.auto_tags.copy()
        scene_db.tag_qualities = scene_tag_qualities

        scene_db.status = 'shot' 
        scene_db.weeks_remaining = 0 

    def calculate_scene_quality(self, scene: Scene, performer_mods: Dict, quality_mods: Dict, stamina_multiplier: int):
        # Pre-calculate all scene-wide modifiers from Thematic tags
        scene_mods = {
            'prod_setting_amplifiers': defaultdict(lambda: 1.0),
            'chemistry_amplifier': 1.0,
            'acting_weight': self.data_manager.game_config.get("scene_quality_base_acting_weight", 0.3), 
            'ds_amplifier': 1.0,
        }
        all_scene_tags = set(scene.global_tags) | set(scene.assigned_tags.keys()) | set(scene.auto_tags)

        for tag_name in all_scene_tags:
            tag_def = self.data_manager.tag_definitions.get(tag_name, {})
            if tag_def.get('type') == 'Thematic':
                if modifier_rules := tag_def.get('scene_wide_modifiers'):
                    for rule in modifier_rules:
                        mod_type = rule.get('type')
                        if mod_type == 'amplify_production_setting':
                            category = rule.get('category')
                            multiplier = rule.get('multiplier', 1.0)
                            if category:
                                current_max = scene_mods['prod_setting_amplifiers'][category]
                                scene_mods['prod_setting_amplifiers'][category] = max(current_max, multiplier)
                        elif mod_type == 'amplify_chemistry_effect':
                            multiplier = rule.get('multiplier', 1.0)
                            scene_mods['chemistry_amplifier'] = max(scene_mods['chemistry_amplifier'], multiplier)
                        elif mod_type == 'shift_acting_weight':
                            # This is a shift, so we add it. 0.05 means acting is 5% more important.
                            shift = rule.get('acting_weight_shift', 0.0)
                            scene_mods['acting_weight'] += shift
                        elif mod_type == 'amplify_dom_sub_effect':
                             multiplier = rule.get('multiplier', 1.0)
                             scene_mods['ds_amplifier'] = max(scene_mods['ds_amplifier'], multiplier)
        
        # Clamp acting weight between configured values
        min_weight = self.data_manager.game_config.get("scene_quality_min_acting_weight", 0.2)
        max_weight = self.data_manager.game_config.get("scene_quality_max_acting_weight", 0.8)
        scene_mods['acting_weight'] = np.clip(scene_mods['acting_weight'], min_weight, max_weight)


        # Use pre-calculated amplifiers for production settings
        total_prod_quality_modifier = 1.0
        if scene.bloc_id:
            bloc_db = self.session.query(ShootingBlocDB).get(scene.bloc_id)
            if bloc_db and bloc_db.production_settings:
                for category, tier_name in bloc_db.production_settings.items():
                    tiers = self.data_manager.production_settings_data.get(category, [])
                    tier_info = next((t for t in tiers if t['tier_name'] == tier_name), None)
                    if tier_info:
                        base_modifier = tier_info.get('quality_modifier', 1.0)
                        amplifier = scene_mods['prod_setting_amplifiers'][category]
                        effect = base_modifier - 1.0
                        amplified_effect = effect * amplifier
                        effective_modifier = 1.0 + amplified_effect
                        total_prod_quality_modifier *= effective_modifier
        
        if overall_mod := quality_mods.get('overall'):
            total_prod_quality_modifier *= overall_mod.get('modifier', 1.0)

        tag_qualities = {}
        performer_contributions_data = [] 
        final_cast_talents = { vp_id: self.talent_service.get_talent_by_id(talent_id) for vp_id, talent_id in scene.final_cast.items() }
        final_cast_talents = {vp_id: t for vp_id, t in final_cast_talents.items() if t}

        if not final_cast_talents:
            return performer_contributions_data, tag_qualities
        
        protagonist_weight = self.data_manager.game_config.get("protagonist_contribution_weight", 1.25)
            
        # Use pre-calculated chemistry amplifier
        base_chemistry_scalar = self.data_manager.game_config.get("chemistry_performance_scalar", 0.125)
        effective_chemistry_scalar = base_chemistry_scalar * scene_mods['chemistry_amplifier']
        net_chemistry_modifiers = defaultdict(int)
        all_talent_in_scene = list(final_cast_talents.values())

        if len(all_talent_in_scene) >= 2:
            for t1, t2 in combinations(all_talent_in_scene, 2):
                score = t1.chemistry.get(t2.id, 0)
                net_chemistry_modifiers[t1.id] += score
                net_chemistry_modifiers[t2.id] += score
            
        action_instance_qualities = defaultdict(list)
        in_scene_penalty_scalar = self.data_manager.game_config.get("in_scene_penalty_scalar", 0.4); fatigue_penalty_scalar = self.data_manager.game_config.get("fatigue_penalty_scalar", 0.3)
        temp_contributions = defaultdict(list)
        vp_map = {vp.id: vp for vp in scene.virtual_performers}
        default_ds_weights = {0: 0.0, 1: 0.2, 2: 0.4, 3: 0.7}
        ds_weights_from_config = self.data_manager.game_config.get("scene_quality_ds_weights", {str(k): v for k, v in default_ds_weights.items()})
        DS_WEIGHTS = {int(k): v for k, v in ds_weights_from_config.items()}
        base_ds_weight = DS_WEIGHTS.get(scene.dom_sub_dynamic_level, 0.0)

        action_segments_for_calc = scene.get_expanded_action_segments(self.data_manager.tag_definitions)
        for i, segment in enumerate(action_segments_for_calc):
            receivers, givers, performers, slot_roles = [], [], [], {}

            for assignment in segment.slot_assignments:
                talent = final_cast_talents.get(str(assignment.virtual_performer_id))
                if not talent: continue
                try: _ , slot_role, _ = assignment.slot_id.rsplit('_', 2)
                except ValueError: logger.warning(f"[WARNING] Could not parse role from slot_id: {assignment.slot_id}"); continue
                if slot_role == "Receiver": receivers.append(talent)
                elif slot_role == "Giver": givers.append(talent)
                elif slot_role == "Performer": performers.append(talent)
                else: logger.warning(f"[WARNING] Unrecognized slot role '{slot_role}' from slot_id: {assignment.slot_id}"); continue
                slot_roles[talent.id] = slot_role
            
            intended_receivers = segment.parameters.get('Receiver', 0)
            intended_givers = segment.parameters.get('Giver', 0)
            intended_performers = segment.parameters.get('Performer', 0)

            min_perf_mod = self.data_manager.game_config.get("scene_quality_min_performance_modifier", 0.1)
            for talent in receivers + givers + performers:
                vp_id_str = next((k for k, v in scene.final_cast.items() if v == talent.id), None)
                vp = vp_map.get(int(vp_id_str)) if vp_id_str else None
                
                performance_modifier = 1.0
                if talent.fatigue > 0: performance_modifier *= (1.0 - (talent.fatigue / 100.0) * fatigue_penalty_scalar)
                max_stamina = talent.stamina * stamina_multiplier
                stamina_cost = scene.performer_stamina_costs.get(str(talent.id), 0.0)
                if stamina_cost > max_stamina and max_stamina > 0: performance_modifier *= (1.0 - ((stamina_cost - max_stamina) / max_stamina) * in_scene_penalty_scalar)
                net_chem_score = net_chemistry_modifiers.get(talent.id, 0)
                performance_modifier *= (1.0 + (net_chem_score * effective_chemistry_scalar)) # --- REFACTOR: Use effective scalar
                
                if performer_mod := performer_mods.get(talent.id):
                    if 'min_mod' in performer_mod and 'max_mod' in performer_mod: performance_modifier *= random.uniform(performer_mod['min_mod'], performer_mod['max_mod'])
                    else: performance_modifier *= performer_mod.get('modifier', 1.0)

                effective_performance = talent.performance * max(min_perf_mod, performance_modifier)
                effective_acting = talent.acting * max(min_perf_mod, performance_modifier)
                
                # Use pre-calculated acting weight for a weighted blend
                acting_weight = scene_mods['acting_weight']
                performance_weight = 1.0 - acting_weight
                base_score = (effective_performance * performance_weight) + (effective_acting * acting_weight)
                
                # Use pre-calculated D/S amplifier
                blended_score = base_score
                tag_def = self.data_manager.tag_definitions.get(segment.tag_name, {})
                ds_multiplier = tag_def.get("dom_sub_multiplier", 1.0) * scene_mods['ds_amplifier']
                effective_ds_weight = min(1.0, base_ds_weight * ds_multiplier)

                if effective_ds_weight > 0 and vp:
                    ds_skill_value = (talent.dom_skill + talent.sub_skill) / 2.0
                    if vp.disposition == "Dom": ds_skill_value = talent.dom_skill
                    elif vp.disposition == "Sub": ds_skill_value = talent.sub_skill
                    blended_score = (base_score * (1 - effective_ds_weight)) + (ds_skill_value * effective_ds_weight)

                performer_weight = 1.0
                if vp_id_str and int(vp_id_str) in scene.protagonist_vp_ids:
                    performer_weight = protagonist_weight

                context_str = "/".join([f"{c}R" for c in [intended_receivers] if c] + [f"{c}G" for c in [intended_givers] if c] + [f"{c}P" for c in [intended_performers] if c])
                contribution_key = f"{segment.tag_name} ({slot_roles[talent.id]}, {context_str})"

                temp_contributions[(talent.id, contribution_key)].append(blended_score)
                action_instance_qualities[segment.tag_name].append((blended_score, performer_weight))
        
        for (talent_id, key), scores in temp_contributions.items():
            performer_contributions_data.append({"talent_id": talent_id, "key": key, "score": round(np.mean(scores), 2)})
        
        for tag_name, quality_data_list in action_instance_qualities.items():
            total_weighted_score = sum(score * weight for score, weight in quality_data_list)
            total_weight = sum(weight for _, weight in quality_data_list)
            if total_weight > 0:
                tag_qualities[tag_name] = round(total_weighted_score / total_weight, 2)
            else:
                tag_qualities[tag_name] = 0.0 # Default if no performers contributed
        
        # --- REFACTOR: PHYSICAL TAG QUALITY CALCULATION ---
        all_cast = list(final_cast_talents.values())
        all_physical_tags = set(scene.assigned_tags.keys()) | set(scene.auto_tags)
        focused_physical_tags = set(scene.assigned_tags.keys())

        for tag_name in all_physical_tags:
            tag_def = self.data_manager.tag_definitions.get(tag_name)
            if not (tag_def and tag_def.get('type') == 'Physical' and all_cast): continue
            
            if tag_name in focused_physical_tags:
                # --- FOCUSED behavior: Calculate quality based on assigned performers ---
                vp_ids = scene.assigned_tags[tag_name]
                assigned_talents = [final_cast_talents.get(str(vp_id)) for vp_id in vp_ids]
                performers_for_quality = [t for t in assigned_talents if t]
                if not performers_for_quality: 
                    tag_qualities[tag_name] = 0.0
                    continue

                if source := tag_def.get('quality_source', {}):
                    quality_data_list = []
                    talent_id_to_vp_id = {v: k for k, v in scene.final_cast.items()}
                    for t in performers_for_quality:
                        score = 0
                        if not (blend_rules := source.get('quality_blend')):
                            score = getattr(t, source.get('base', 'acting'), 0)
                        else:
                            for rule in blend_rules:
                                rule_source, weight = rule.get('source'), rule.get('weight', 1.0)
                                if rule_source == 'static': score += rule.get('value', 0) * weight
                                elif rule_source == 'affinity': score += t.tag_affinities.get(source.get('affinity', tag_def.get('name')), 0) * weight
                                elif rule_source == 'base': score += getattr(t, source.get('base', 'acting'), 0) * weight
                                elif rule_source == 'dick_size': score += (getattr(t, 'dick_size', 0) or 0) * rule.get('multiplier', 1.0) * weight
                        vp_id_str = talent_id_to_vp_id.get(t.id)
                        performer_weight = 1.0
                        if vp_id_str and int(vp_id_str) in scene.protagonist_vp_ids:
                            performer_weight = protagonist_weight
                        
                        quality_data_list.append((score, performer_weight))

                    # Calculate the weighted average for the tag's quality
                    total_weighted_score = sum(score * weight for score, weight in quality_data_list)
                    total_weight = sum(weight for _, weight in quality_data_list)
                    tag_qualities[tag_name] = round(total_weighted_score / total_weight, 2) if total_weight > 0 else 0.0
            
            else:
                # --- AUTO behavior: Quality defaults to value from config ---
                default_quality = self.data_manager.game_config.get("scene_quality_auto_tag_default_quality", 100.0)
                tag_qualities[tag_name] = default_quality
        
        # Apply the final production quality modifier to all scores
        if total_prod_quality_modifier != 1.0:
            for key in tag_qualities:
                tag_qualities[key] = round(tag_qualities[key] * total_prod_quality_modifier, 2)
            
            for contribution in performer_contributions_data:
                contribution['score'] = round(contribution['score'] * total_prod_quality_modifier, 2)

        return performer_contributions_data, tag_qualities

    def apply_post_production_effects(self, scene_db: SceneDB):
        """
        Calculates and applies quality modifiers from post-production choices
        and finalizes the scene for release.
        """
        bloc_db = self.session.query(ShootingBlocDB).get(scene_db.bloc_id) if scene_db.bloc_id else None
        
        editing_tier_id = (scene_db.post_production_choices or {}).get('editing_tier')
        if not editing_tier_id:
            scene_db.status = 'ready_to_release'
            return

        editing_options = self.data_manager.post_production_data.get('editing_tiers', [])
        tier_data = next((t for t in editing_options if t['id'] == editing_tier_id), None)
        if not tier_data:
            scene_db.status = 'ready_to_release'
            return
            
        final_modifier = tier_data.get('base_quality_modifier', 1.0)
        default_camera_tier = self.data_manager.game_config.get("default_camera_setup_tier", "1")
        camera_setup_tier = default_camera_tier
        if bloc_db and bloc_db.production_settings:
            camera_setup_tier = bloc_db.production_settings.get('Camera Setup', default_camera_tier)

        synergy_mod = tier_data.get('synergy_mods', {}).get(camera_setup_tier, 0.0)
        final_modifier += synergy_mod

        if scene_db.tag_qualities:
            modified_tags = scene_db.tag_qualities.copy()
            for tag, quality in modified_tags.items():
                modified_tags[tag] = round(quality * final_modifier, 2)
            scene_db.tag_qualities = modified_tags
            flag_modified(scene_db, "tag_qualities")

        for contrib in scene_db.performer_contributions_rel:
            contrib.quality_score = round(contrib.quality_score * final_modifier, 2)
        
        mod_details = scene_db.revenue_modifier_details.copy() if scene_db.revenue_modifier_details else {}
        mod_details[f"Editing ({tier_data.get('name')})"] = round(final_modifier, 2)
        scene_db.revenue_modifier_details = mod_details
        flag_modified(scene_db, "revenue_modifier_details")

        scene_db.status = 'ready_to_release'

    def calculate_revenue(self, scene: Scene) -> int:
        total_revenue = 0
        scene.viewer_group_interest.clear()
        scene.revenue_modifier_details.clear()
        base_revenue = self.data_manager.game_config.get("base_release_revenue", 50000)

        # --- Calculate Tag Weights ---
        all_tags_with_weights = {}
        focused_weight = self.data_manager.game_config.get("revenue_weight_focused_physical_tag", 5.0)
        # Physical tags (player-assigned)
        for tag_name in scene.assigned_tags:
            tag_def = self.data_manager.tag_definitions.get(tag_name, {})
            all_tags_with_weights[tag_name] = tag_def.get('revenue_weights', {}).get('focused', focused_weight)
        # Action tags
        default_action_weight = self.data_manager.game_config.get("revenue_weight_default_action_appeal", 10.0)
        action_segments_for_calc = scene.get_expanded_action_segments(self.data_manager.tag_definitions)
        for segment in action_segments_for_calc:
            unique_key = f"{segment.tag_name}_{segment.id}"
            tag_def = self.data_manager.tag_definitions.get(segment.tag_name, {})
            appeal_weight = tag_def.get('appeal_weight') or default_action_weight
            all_tags_with_weights[unique_key] = (segment.runtime_percentage / 100.0) * appeal_weight
        # Auto tags
        auto_weight = self.data_manager.game_config.get("revenue_weight_auto_tag", 1.5)
        focused_tags = set(scene.global_tags) | set(scene.assigned_tags.keys())
        for tag_name in scene.auto_tags:
            if tag_name not in focused_tags:
                tag_def = self.data_manager.tag_definitions.get(tag_name, {})
                all_tags_with_weights[tag_name] = tag_def.get('revenue_weights', {}).get('auto', auto_weight)

        if total_weight := sum(all_tags_with_weights.values()):
            all_tags_with_weights = {k: v / total_weight for k, v in all_tags_with_weights.items()}

        cast_talents = [self.talent_service.get_talent_by_id(tid) for tid in scene.final_cast.values() if tid]
        all_market_states = self.market_service.get_all_market_states()

        for group in self.data_manager.market_data.get('viewer_groups', []):
            group_name = group.get('name')
            if not group_name: continue
            
            resolved_group_data = self.market_service.get_resolved_group_data(group_name)
            prefs = resolved_group_data.get('preferences', {})
            
            # 1. Calculate ADDITIVE Thematic Appeal
            additive_appeal = 0.0
            thematic_prefs = prefs.get('thematic_sentiments', {})
            for tag_name in scene.global_tags: # Thematic tags live in global_tags
                additive_appeal += thematic_prefs.get(tag_name, 0.0)

            # 2. Calculate MULTIPLICATIVE Content Appeal
            multiplicative_appeal = 0.0
            phys_prefs = prefs.get('physical_sentiments', {})
            act_prefs = prefs.get('action_sentiments', {})
            orient_prefs = prefs.get('orientation_sentiments', {})
            scaling_rules = prefs.get('scaling_sentiments', {})
            default_sentiment = self.data_manager.game_config.get("default_sentiment_multiplier", 1.0)
            
            for tag_key, weight in all_tags_with_weights.items():
                full_tag_name = tag_key.split('_')[0]
                tag_def = self.data_manager.tag_definitions.get(full_tag_name, {})
                tag_type = tag_def.get('type')

                if tag_type == 'Thematic': continue

                # Get quality: auto is 100, focused physical and action are calculated
                quality = scene.tag_qualities.get(full_tag_name, 100.0) / 100.0
                
                pref_multiplier = default_sentiment
                if tag_type == 'Physical': pref_multiplier = phys_prefs.get(full_tag_name, default_sentiment)
                elif tag_type == 'Action': pref_multiplier = act_prefs.get(full_tag_name, default_sentiment)
                
                if orientation := tag_def.get('orientation'):
                    pref_multiplier *= orient_prefs.get(orientation, 1.0)

                # Scaling sentiments
                if segment := next((s for s in action_segments_for_calc if f"{s.tag_name}_{s.id}" == tag_key), None):
                    base_name, concept = tag_def.get('name'), tag_def.get('concept')
                    rule = scaling_rules.get(full_tag_name) or (scaling_rules.get(base_name) if base_name else None) or (scaling_rules.get(concept) if concept else None)
                    if isinstance(rule, dict):
                        count = segment.parameters.get(rule.get("based_on_role"), 0)
                        bonus, penalty = 0.0, 0.0
                        if count > (applies_after := rule.get("applies_after", 0)):
                            units = count - applies_after
                            if "bonuses" in rule: bonus = sum(rule["bonuses"][min(i, len(rule["bonuses"]) - 1)] for i in range(units))
                            elif "bonus_per_unit" in rule: bonus = units * rule["bonus_per_unit"]
                        if (penalty_after := rule.get("penalty_after")) is not None and count > penalty_after:
                            penalty = (count - penalty_after) * rule.get("penalty_per_unit", 0)
                        pref_multiplier *= (1.0 + bonus - penalty)

                multiplicative_appeal += (quality * pref_multiplier * weight)

            # 3. Combine and Finalize Score
            group_interest_score = multiplicative_appeal + additive_appeal

            # Apply D/S dynamic preferences
            ds_sentiments = prefs.get('dom_sub_sentiments', {})
            ds_multiplier = ds_sentiments.get(str(scene.dom_sub_dynamic_level), 1.0)
            group_interest_score *= ds_multiplier

            if cast_talents:
                avg_pop = np.mean([t.popularity.get(group_name, 0.0) for t in cast_talents])
                star_power_bonus = 1.0 + (avg_pop * self.data_manager.game_config.get("star_power_revenue_scalar", 0.005))
                group_interest_score *= star_power_bonus
                if star_power_bonus > 1.0: scene.revenue_modifier_details[f"Star Power ({group_name})"] = round(star_power_bonus, 2)
            if scene.focus_target == group_name: group_interest_score *= resolved_group_data.get('focus_bonus', 1.0)
            
            scene.viewer_group_interest[group_name] = round(group_interest_score, 4)
            if group_interest_score > 0:
                dynamic_state = all_market_states.get(group_name)
                saturation = dynamic_state.current_saturation if dynamic_state else 1.0
                market_share = resolved_group_data.get('market_share_percent', 0) / 100.0
                spending_power = resolved_group_data.get('spending_power', 1.0)
                total_revenue += (base_revenue * market_share) * group_interest_score * spending_power * saturation
                if dynamic_state:
                    saturation_cost = group_interest_score * self.data_manager.game_config.get("saturation_spend_rate", 0.15)
                    market_state_db = self.session.query(MarketGroupStateDB).get(group_name)
                    if market_state_db:
                        market_state_db.current_saturation = max(0, market_state_db.current_saturation - saturation_cost)
        
        penalty_config = self.data_manager.game_config.get("revenue_penalties", {})
        final_penalty_multiplier = 1.0

        short_scene_config = penalty_config.get("short_scene", {})
        if short_scene_config.get("enabled", False):
            no_penalty_minutes = short_scene_config.get("no_penalty_minutes", 10)
            if scene.total_runtime_minutes < no_penalty_minutes:
                max_penalty_minutes = short_scene_config.get("max_penalty_minutes", 1); max_penalty_mult = short_scene_config.get("max_penalty_multiplier", 0.30)
                short_scene_mult = np.interp(scene.total_runtime_minutes, [max_penalty_minutes, no_penalty_minutes], [max_penalty_mult, 1.0])
                final_penalty_multiplier *= short_scene_mult; scene.revenue_modifier_details["Short Scene Penalty"] = round(short_scene_mult, 2)
        long_scene_config = penalty_config.get("long_monotonous_scene", {})
        if long_scene_config.get("enabled", False):
            min_runtime = long_scene_config.get("min_runtime_minutes_for_penalty", 40)
            if scene.total_runtime_minutes > min_runtime:
                unique_concepts = set()
                for segment in action_segments_for_calc:
                    tag_def = self.data_manager.tag_definitions.get(segment.tag_name, {}); concept = tag_def.get('concept', segment.tag_name)
                    unique_concepts.add(concept)
                num_unique_concepts = len(unique_concepts); concepts_per_10_min = num_unique_concepts / (scene.total_runtime_minutes / 10.0)
                target_concepts = long_scene_config.get("target_concepts_per_10_min", 0.8)
                if concepts_per_10_min < target_concepts:
                    max_penalty_mult = long_scene_config.get("max_penalty_multiplier", 0.65)
                    monotony_mult = np.interp(concepts_per_10_min, [0, target_concepts], [max_penalty_mult, 1.0])
                    final_penalty_multiplier *= monotony_mult; scene.revenue_modifier_details["Monotony Penalty"] = round(monotony_mult, 2)
        overstuffed_config = penalty_config.get("overstuffed_scene", {})
        if overstuffed_config.get("enabled", False):
            min_runtime = overstuffed_config.get("min_runtime_minutes_for_penalty", 15)
            if scene.total_runtime_minutes >= min_runtime:
                all_scene_tags = set(scene.global_tags) | set(scene.assigned_tags.keys())
                for segment in action_segments_for_calc: all_scene_tags.add(segment.tag_name)
                unique_concepts = set()
                for tag_name in all_scene_tags:
                    tag_def = self.data_manager.tag_definitions.get(tag_name, {}); concept = tag_def.get('concept', tag_name)
                    unique_concepts.add(concept)
                num_unique_concepts = len(unique_concepts); tags_per_10_min = num_unique_concepts / (scene.total_runtime_minutes / 10.0)
                threshold = overstuffed_config.get("penalty_threshold_tags_per_10_min", 3.0)
                if tags_per_10_min > threshold:
                    max_penalty_mult = overstuffed_config.get("max_penalty_multiplier", 0.75); max_density = overstuffed_config.get("max_penalty_tags_per_10_min", 6.0)
                    clamped_density = min(tags_per_10_min, max_density); overstuffed_mult = np.interp(clamped_density, [threshold, max_density], [1.0, max_penalty_mult])
                    final_penalty_multiplier *= overstuffed_mult; scene.revenue_modifier_details["Overstuffed Scene Penalty"] = round(overstuffed_mult, 2)

        return int(total_revenue * final_penalty_multiplier)

    
    def _analyze_cast_composition(self, scene: Scene) -> Dict[str, float]:
        cast_talents = [t for t in [self.talent_service.get_talent_by_id(tid) for tid in scene.final_cast.values()] if t]
        if not cast_talents:
            return {}

        focused_tags = set(scene.global_tags) | set(scene.assigned_tags.keys())
        discovered_tags = {}

        candidate_tags = [
            (full_name, tag_def) for full_name, tag_def in self.data_manager.tag_definitions.items()
            if tag_def.get('type') == 'Physical' and tag_def.get('is_auto_taggable')
        ]

        for full_name, tag_def in candidate_tags:
            if full_name in focused_tags or full_name in discovered_tags:
                continue
            # Case 1: Multi-performer compositional tag (e.g., Interracial, Age Gap)
            if validation_rule := tag_def.get('validation_rule'):
                if self._validate_compositional_tag(cast_talents, validation_rule):
                    discovered_tags[full_name] = 100.0
            
            # Case 2: Single-performer attribute tag (e.g., MILF, Big Dick)
            elif detection_rule := tag_def.get('auto_detection_rule'):
                # Pre-filter cast based on top-level gender/ethnicity
                potential_performers = [
                    t for t in cast_talents
                    if (not tag_def.get('gender') or t.gender == tag_def.get('gender')) and
                       (not tag_def.get('ethnicity') or t.ethnicity == tag_def.get('ethnicity'))
                ]
                if not potential_performers:
                    continue

                # Check if ANY performer meets all conditions
                for performer in potential_performers:
                    if self._check_performer_conditions(performer, detection_rule):
                        discovered_tags[full_name] = 100.0
                        break # Found one, tag is added, move to next tag
                        
        return discovered_tags

    
    def _check_performer_conditions(self, performer: Talent, rule: Dict) -> bool:
        """Helper function to check if a single performer meets all conditions in a rule."""
        conditions = rule.get("conditions", []) 
        if not conditions:
            return False

        for cond in conditions:
            cond_type = (cond.get('type') or '').lower()
            key = cond.get('key')
            comparison = cond.get('comparison')
            value = cond.get('value')
            
            actual_value = None
            if cond_type == 'stat':
                actual_value = getattr(performer, key, None)
            elif cond_type == 'affinity':
                actual_value = performer.tag_affinities.get(key)
            elif cond_type == 'physical':
                actual_value = getattr(performer, key, None)
            if actual_value is None:
                return False

            is_met = False
            if comparison == 'gte' and actual_value >= value: is_met = True
            elif comparison == 'lte' and actual_value <= value: is_met = True
            elif comparison == 'eq' and actual_value == value: is_met = True
            elif comparison == 'in' and actual_value in value: is_met = True
            
            if not is_met:
                return False
        return True

    def _validate_compositional_tag(self, cast: List[Talent], rule: Dict) -> Optional[List[Talent]]:
        profiles = rule.get("profiles", [])
        if not profiles or len(cast) < len(profiles): return None
        # Using permutations is computationally expensive, but necessary for correctness with small cast sizes.
        # For larger scenes, this could be optimized if it becomes a bottleneck.
        for cast_permutation in permutations(cast, len(profiles)):
            matched_performers, is_valid_permutation = [], True
            for i, profile in enumerate(profiles):
                performer = cast_permutation[i]
                if (profile.get("gender") and performer.gender != profile.get("gender")) or \
                   (profile.get("ethnicity") and performer.ethnicity != profile.get("ethnicity")) or \
                   (profile.get("min_age") is not None and performer.age < profile.get("min_age")) or \
                   (profile.get("max_age") is not None and performer.age > profile.get("max_age")):
                    is_valid_permutation = False; break
                matched_performers.append(performer)
            
            if not is_valid_permutation: continue
            
            if "min_gap_years" in rule:
                # Find performers matched to roles to check the age gap
                older = next((p for i, p in enumerate(matched_performers) if profiles[i].get("role") == "older"), None)
                younger = next((p for i, p in enumerate(matched_performers) if profiles[i].get("role") == "younger"), None)
                if not (older and younger and (older.age - younger.age) >= rule["min_gap_years"]):
                    continue # This permutation doesn't meet the age gap, try the next one

            return matched_performers # Found a valid permutation
        
        return None