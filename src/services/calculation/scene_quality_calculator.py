import logging
import random
import numpy as np
from collections import defaultdict
from itertools import combinations
from typing import Dict, List, Tuple, Any

from data.game_state import Scene, Talent
from data.data_manager import DataManager
from services.models.configs import SceneCalculationConfig
from services.models.results import SceneQualityResult
from services.calculation.budget_efficiency_calculator import BudgetEfficiencyCalculator

logger = logging.getLogger(__name__)

class SceneQualityCalculator:
    """
    Critical, pure calculation service that acts as the final arbiter of a
    scene's quality score. Calculates all aspects of scene quality,
    including tag qualities, performer contributions, and technical execution.
    """
    def __init__(self, data_manager: DataManager, config: SceneCalculationConfig,
                 budget_efficiency_calculator: BudgetEfficiencyCalculator):
        self.data_manager = data_manager
        self.config = config
        self.budget_efficiency_calculator = budget_efficiency_calculator

    def calculate_quality(
        self, scene: Scene, cast_talents: List[Talent], 
        shoot_modifiers: Dict, bloc_data: Dict | None
    ) -> SceneQualityResult:
        """
        Calculates the final quality scores for a scene after it has been shot.

        Process:
        1. Calculate scene-wide modifiers from thematic tags (Weights, Chemistry amplifies).
        2. Calculate Action Tag qualities and Performer Contributions.
        3. Calculate Physical Tag qualities.
        4. Calculate Technical Score Multiplier using Weighted Averages of Production Cache.
        5. Apply multiplier to all base scores.
        """
        if not cast_talents:
            return SceneQualityResult(tag_qualities={}, performer_contributions=[])

        performer_mods = shoot_modifiers.get('performer_mods', {})
        quality_mods = shoot_modifiers.get('quality_mods', {})

        final_cast_talents_by_vp_id = {
            vp_id: next((t for t in cast_talents if t.id == talent_id), None)
            for vp_id, talent_id in scene.final_cast.items()
        }
        final_cast_talents_by_vp_id = {vp_id: t for vp_id, t in final_cast_talents_by_vp_id.items() if t}

        # 1. Calculate scene-wide modifiers (from Thematic tags, etc.)
        scene_mods = self._calculate_scene_wide_modifiers(scene)

        # 2. Calculate Action Tag qualities and Performer Contributions
        action_tag_qualities, performer_contributions_data = self._calculate_action_tag_qualities(
            scene, final_cast_talents_by_vp_id, scene_mods, performer_mods
        )

        # 3. Calculate Physical Tag qualities
        physical_tag_qualities = self._calculate_physical_tag_qualities(scene, final_cast_talents_by_vp_id)

        # 4. Combine all tag qualities
        tag_qualities = {**action_tag_qualities, **physical_tag_qualities}

        # 5. Calculate and apply the final production quality modifier
        # This uses the new Weighted Average system based on cache and tags
        total_prod_quality_modifier = self._calculate_technical_score_multiplier(
            scene, bloc_data, scene_mods
        )
    
        if overall_mod := quality_mods.get('overall'):
            total_prod_quality_modifier *= overall_mod.get('modifier', 1.0)

        # Apply Modifier to all scores
        if total_prod_quality_modifier != 1.0:
            for key in tag_qualities:
                tag_qualities[key] = round(tag_qualities[key] * total_prod_quality_modifier, 2)
            
            for contribution in performer_contributions_data:
                contribution['quality_score'] = round(contribution['quality_score'] * total_prod_quality_modifier, 2)

        return SceneQualityResult(
            tag_qualities=tag_qualities,
            performer_contributions=performer_contributions_data
        )

    def _calculate_scene_wide_modifiers(self, scene: Scene) -> Dict:
        """
        Calculates scene-wide quality modifiers by aggregating effects from all Thematic tags.
        Also aggregates Department Weight Modifiers.
        """
        scene_mods = {
            'prod_setting_amplifiers': defaultdict(lambda: 1.0), 
            'chemistry_amplifier': 1.0, 
            'acting_weight': self.config.scene_quality_base_acting_weight, 
            'ds_amplifier': 1.0,
            'department_weight_mods': defaultdict(float) # New: Stores adds/subs to department weights
        }
        all_scene_tags = set(scene.global_tags) | set(scene.assigned_tags.keys()) | set(scene.auto_tags) 

        for tag_name in all_scene_tags:
            tag_def = self.data_manager.tag_definitions.get(tag_name, {})
            if tag_def.get('type') == 'Thematic':
                if modifier_rules := tag_def.get('scene_wide_modifiers'):
                    for rule in modifier_rules:
                        mod_type = rule.get('type')
                        
                        if mod_type == 'modify_department_weight':
                            dept = rule.get('department')
                            weight_add = rule.get('weight_add', 0.0)
                            if dept:
                                scene_mods['department_weight_mods'][dept] += weight_add

                        elif mod_type == 'amplify_production_setting':
                            category = rule.get('category')
                            multiplier = rule.get('multiplier', 1.0)
                            if category:
                                current_max = scene_mods['prod_setting_amplifiers'][category]
                                scene_mods['prod_setting_amplifiers'][category] = max(current_max, multiplier)
                                
                        elif mod_type == 'amplify_chemistry_effect':
                            multiplier = rule.get('multiplier', 1.0)
                            scene_mods['chemistry_amplifier'] = max(scene_mods['chemistry_amplifier'], multiplier)
                            
                        elif mod_type == 'shift_acting_weight':
                            shift = rule.get('acting_weight_shift', 0.0)
                            scene_mods['acting_weight'] += shift
                            
                        elif mod_type == 'amplify_dom_sub_effect':
                             multiplier = rule.get('multiplier', 1.0)
                             scene_mods['ds_amplifier'] = max(scene_mods['ds_amplifier'], multiplier)
        
        scene_mods['acting_weight'] = np.clip(scene_mods['acting_weight'], self.config.scene_quality_min_acting_weight, self.config.scene_quality_max_acting_weight)
        return scene_mods

    def _calculate_technical_score_multiplier(self, scene: Scene, bloc_data: Dict | None, scene_mods: Dict) -> float:
        """
        Calculates the Weighted Average Technical Score of the scene.
        
        Algorithm:
        1. Iterate all production slots (Resources & Crew).
        2. Determine Base Weight for each slot (from JSON).
        3. Apply Modifiers:
           - Tag Modifiers (e.g. Cosplay adds to Wardrobe).
           - Audio Rule: Audio weight scales with Acting Weight.
        4. Fetch Score (0-100) from production_cache.
        5. Compute Weighted Average.
        6. Convert Average (0-100) to Multiplier (e.g. 50 -> 1.0, 100 -> 1.5).
        """
        if not bloc_data:
            return 1.0

        production_cache = bloc_data.get('production_cache', {})
        crew_assignments = bloc_data.get('crew_assignments', {})
        dept_weight_mods = scene_mods.get('department_weight_mods', {})
        
        total_weight = 0.0
        weighted_score_sum = 0.0
        
        # 1. Gather all active slots from the cache (Resources + Generic Crew)
        # Note: We rely on the cache keys to know what was "paid for".
        # Character Crew (if any) are in crew_assignments but might not be in cache if handled differently.
        # For now, we assume if it's contributing to tech score, it has a score resolved.
        
        # We also need to check crew_assignments to catch slots that might use Characters
        all_slots = set(production_cache.keys()) | set(crew_assignments.keys())
        
        for slot_id in all_slots:
            # 2. Determine Base Weight
            base_weight, impacts_tech = self._get_slot_weight_and_impact(slot_id)
            
            if not impacts_tech or base_weight <= 0:
                continue

            # 3. Apply Modifiers
            final_weight = base_weight
            
            # A. Tag Modifiers
            if slot_id in dept_weight_mods:
                final_weight += dept_weight_mods[slot_id]
            
            # B. Audio Dynamic Rule
            # Audio importance scales with dialogue (acting weight)
            if slot_id == 'audio_equipment':
                # Ratio: Current Acting Weight / Base Acting Weight
                # e.g., 0.5 / 0.3 = 1.66x importance
                ratio = scene_mods['acting_weight'] / self.config.scene_quality_base_acting_weight
                final_weight *= ratio

            if final_weight <= 0:
                continue

            # 4. Fetch Score
            score = 0
            assignment = crew_assignments.get(slot_id, {})
            
            # Case A: Generic or Resource (In Cache)
            if slot_id in production_cache:
                score = production_cache[slot_id]
            
            # Case B: Named Character (Future Proofing)
            elif assignment.get('type') == 'character':
                # TODO: Resolve character skill from DB/Context
                # For now, fallback to cache or average
                score = production_cache.get(slot_id, 50)
            
            weighted_score_sum += (score * final_weight)
            total_weight += final_weight

        if total_weight == 0:
            return 1.0

        # 5. Compute Weighted Average
        average_score = weighted_score_sum / total_weight
        
        # 6. Convert to Multiplier
        # Baseline: 50/100 -> 1.0x
        # Max: 100/100 -> 1.5x (Configurable?)
        # Min: 0/100 -> 0.5x
        # Formula: 0.5 + (Score / 100)
        multiplier = 0.5 + (average_score / 100.0)
        
        return max(0.1, multiplier)

    def _get_slot_weight_and_impact(self, slot_id: str) -> Tuple[float, bool]:
        """
        Helper to find the base weight and tech impact flag for any slot ID
        (checking both Departments and Jobs).
        """
        # Check Departments
        dept_def = self.data_manager.production_departments.get(slot_id)
        if dept_def:
            impacts = dept_def.get('impacts', [])
            return dept_def.get('base_weight', 0.0), ('tech_score' in impacts)
        
        # Check Jobs
        job_def = self.data_manager.production_jobs.get(slot_id)
        if job_def:
            impacts = job_def.get('impacts', [])
            return job_def.get('base_weight', 0.0), ('tech_score' in impacts)
            
        # Fallback for Location Logistics (Dynamic)
        if slot_id == 'location_logistics':
            # Location usually impacts tech score implicitly via stress/momentum,
            # but if we want it to weigh in the visual quality directly:
            return 0.2, True 

        return 0.0, False

    def _calculate_action_tag_qualities(self, scene: Scene, final_cast_talents: Dict, scene_mods: Dict, performer_mods: Dict) -> Tuple[Dict, List[Dict]]:
        """
        Calculates quality scores for all Action tags by aggregating the individual
        contributions of each performer within each action segment.

        The process for each performer in a segment is as follows:
        1.  Calculate a 'performance_modifier' based on fatigue, stamina overdraw,
            cast chemistry, and event modifiers.
        2.  Calculate a 'base_score' by blending the talent's effective Performance and Acting skills.
        3.  Calculate a 'blended_score' by further blending the 'base_score' with the
            talent's Dom/Sub skill, based on the scene's D/S level.
        4.  This score contributes to both the final Action Tag quality (as a weighted average
            where protagonists count more) and the list of individual performer contributions.

        Args:
            scene: The scene being calculated.
            final_cast_talents: A dict mapping virtual performer IDs to Talent objects.
            scene_mods: Pre-calculated scene-wide modifiers.
            performer_mods: A dict of event-based modifiers for specific performers.

        Returns:
            A tuple containing:
            - A dict of final Action Tag qualities (tag_name -> score).
            - A list of detailed performer contribution dicts.
        """
        action_instance_qualities = defaultdict(list)
        temp_contributions = defaultdict(list)
        vp_map = {vp.id: vp for vp in scene.virtual_performers}
        final_cast_talents_by_id = {t.id: t for t in final_cast_talents.values()}

        # Sum up chemistry scores for each performer
        effective_chemistry_scalar = self.config.chemistry_performance_scalar * scene_mods['chemistry_amplifier']
        net_chemistry_modifiers = defaultdict(int)
        all_talent_in_scene = list(final_cast_talents.values())
        if len(all_talent_in_scene) >= 2:
            for t1, t2 in combinations(all_talent_in_scene, 2):
                score = t1.chemistry.get(str(t2.id), 0)
                net_chemistry_modifiers[t1.id] += score
                net_chemistry_modifiers[t2.id] += score

        base_ds_weight = self.config.scene_quality_ds_weights.get(scene.dom_sub_dynamic_level, 0.0)
        expanded_segments = scene.get_expanded_action_segments(self.data_manager.tag_definitions)

        for i, segment in enumerate(expanded_segments):
            slot_roles = {}
            # Rebuild talent lists for this segment based on final_cast_talents
            talents_in_segment = []
            for assignment in segment.slot_assignments:
                talent = final_cast_talents.get(str(assignment.virtual_performer_id))
                if not talent: continue
                talents_in_segment.append(talent)
                try: _, slot_role, _ = assignment.slot_id.rsplit('_', 2)
                except ValueError: logger.warning(f"Could not parse role from slot_id: {assignment.slot_id}"); continue
                slot_roles[talent.id] = slot_role
            
            for talent in talents_in_segment:
                vp_id_str = next((k for k, v in scene.final_cast.items() if v == talent.id), None)
                vp = vp_map.get(int(vp_id_str)) if vp_id_str else None
                
                # --- 1. Calculate the core performance modifier ---
                performance_modifier = 1.0
                # Apply penalties for fatigue and stamina overdraw
                if talent.fatigue > 0: performance_modifier *= (1.0 - (talent.fatigue / 100.0) * self.config.fatigue_penalty_scalar)
                max_stamina = talent.stamina * self.config.stamina_to_pool_multiplier
                stamina_cost = scene.performer_stamina_costs.get(str(talent.id), 0.0)
                if stamina_cost > max_stamina and max_stamina > 0: performance_modifier *= (1.0 - ((stamina_cost - max_stamina) / max_stamina) * self.config.in_scene_penalty_scalar)
                # Apply boosts from cast chemistry and random events
                net_chem_score = net_chemistry_modifiers.get(talent.id, 0)
                performance_modifier *= (1.0 + (net_chem_score * effective_chemistry_scalar))
                
                if performer_mod := performer_mods.get(talent.id):
                    if 'min_mod' in performer_mod and 'max_mod' in performer_mod: performance_modifier *= random.uniform(performer_mod['min_mod'], performer_mod['max_mod'])
                    else: performance_modifier *= performer_mod.get('modifier', 1.0)

                # --- 2. Calculate base score from Acting/Performance blend ---
                effective_performance = talent.performance * max(self.config.scene_quality_min_performance_modifier, performance_modifier)
                effective_acting = talent.acting * max(self.config.scene_quality_min_performance_modifier, performance_modifier)
                
                acting_weight = scene_mods['acting_weight']
                performance_weight = 1.0 - acting_weight
                base_score = (effective_performance * performance_weight) + (effective_acting * acting_weight)
                
                # --- 3. Blend base score with D/S skill ---
                blended_score = base_score
                tag_def = self.data_manager.tag_definitions.get(segment.tag_name, {})
                ds_multiplier = tag_def.get("dom_sub_multiplier", 1.0) * scene_mods['ds_amplifier']
                effective_ds_weight = min(1.0, base_ds_weight * ds_multiplier)

                if effective_ds_weight > 0 and vp:
                    ds_skill_value = (talent.dom_skill + talent.sub_skill) / 2.0
                    if vp.disposition == "Dom": ds_skill_value = talent.dom_skill
                    elif vp.disposition == "Sub": ds_skill_value = talent.sub_skill
                    blended_score = (base_score * (1 - effective_ds_weight)) + (ds_skill_value * effective_ds_weight)

                # --- 4. Store score for aggregation ---
                performer_weight = 1.0
                if vp_id_str and int(vp_id_str) in scene.protagonist_vp_ids:
                    performer_weight = self.config.protagonist_contribution_weight

                intended_receivers = segment.parameters.get('Receiver', 0)
                intended_givers = segment.parameters.get('Giver', 0)
                intended_performers = segment.parameters.get('Performer', 0)
                context_str = "/".join([f"{c}R" for c in [intended_receivers] if c] + [f"{c}G" for c in [intended_givers] if c] + [f"{c}P" for c in [intended_performers] if c])
                contribution_key = f"{segment.tag_name} ({slot_roles[talent.id]}, {context_str})"

                temp_contributions[(talent.id, contribution_key)].append(blended_score)
                action_instance_qualities[segment.tag_name].append((blended_score, performer_weight))
        
        # Aggregate scores for final contributions list
        final_contributions = []
        for (talent_id, key), scores in temp_contributions.items():
            final_contributions.append({
                "talent_id": talent_id, 
                "contribution_key": key, 
                "quality_score": round(np.mean(scores), 2)
            })
        
        # Aggregate scores for final tag qualities (weighted average)
        final_tag_qualities = {}
        for tag_name, quality_data_list in action_instance_qualities.items():
            total_weighted_score = sum(score * weight for score, weight in quality_data_list)
            total_weight = sum(weight for _, weight in quality_data_list)
            final_tag_qualities[tag_name] = round(total_weighted_score / total_weight, 2) if total_weight > 0 else 0.0
        return final_tag_qualities, final_contributions

    def _calculate_physical_tag_qualities(self, scene: Scene, final_cast_talents: Dict) -> Dict:
        """
        Calculates quality scores for all Physical tags in a scene.

        It differentiates between:
        - "Focused" tags (manually added by the player): Quality is calculated based
          on the assigned performers' attributes, driven by the `quality_source`
          rules in the tag definition. This can be a simple stat or a complex blend.
        - "Auto" tags (discovered during shoot): These are assigned a default quality score
          from the config, as they represent background attributes rather than a focus.

        Args:
            scene: The scene being calculated.
            final_cast_talents: A dict mapping virtual performer IDs to Talent objects.

        Returns:
            A dictionary of physical tag qualities (tag_name -> score).
        """
        physical_tag_qualities = {}
        all_physical_tags = set(scene.assigned_tags.keys()) | set(scene.auto_tags)
        focused_physical_tags = set(scene.assigned_tags.keys())
        all_cast = list(final_cast_talents.values())

        for tag_name in all_physical_tags:
            tag_def = self.data_manager.tag_definitions.get(tag_name)
            if not (tag_def and tag_def.get('type') == 'Physical' and all_cast): continue
            
            if tag_name in focused_physical_tags:
                vp_ids = scene.assigned_tags[tag_name]
                assigned_talents = [final_cast_talents.get(str(vp_id)) for vp_id in vp_ids]
                performers_for_quality = [t for t in assigned_talents if t]
                if not performers_for_quality: 
                    physical_tag_qualities[tag_name] = 0.0
                    continue

                # The 'quality_source' in the tag definition is a powerful, data-driven
                # way to define how quality is calculated for this specific tag.
                if source := tag_def.get('quality_source', {}):
                    quality_data_list = []
                    talent_id_to_vp_id = {v.id: k for k, v in final_cast_talents.items()}
                    for t in performers_for_quality:
                        score = 0
                        if not (blend_rules := source.get('quality_blend')):
                            # Simple case: quality is based on a single attribute.
                            score = getattr(t, source.get('base', 'acting'), 0)
                        else:
                            # Complex case: blend multiple sources.
                            for rule in blend_rules:
                                rule_source, weight = rule.get('source'), rule.get('weight', 1.0)
                                if rule_source == 'static': score += rule.get('value', 0) * weight
                                elif rule_source == 'affinity': score += t.tag_affinities.get(source.get('affinity', tag_def.get('name')), 0) * weight
                                elif rule_source == 'base': score += getattr(t, source.get('base', 'acting'), 0) * weight
                                elif rule_source == 'dick_size': score += (getattr(t, 'dick_size', 0) or 0) * rule.get('multiplier', 1.0) * weight
                        
                        # Apply protagonist weight
                        vp_id_str = talent_id_to_vp_id.get(t.id)
                        performer_weight = 1.0
                        if vp_id_str and int(vp_id_str) in scene.protagonist_vp_ids:
                            performer_weight = self.config.protagonist_contribution_weight
                        quality_data_list.append((score, performer_weight))

                    # Final quality is the weighted average of all performers' scores
                    total_weighted_score = sum(score * weight for score, weight in quality_data_list)
                    total_weight = sum(weight for _, weight in quality_data_list)
                    physical_tag_qualities[tag_name] = round(total_weighted_score / total_weight, 2) if total_weight > 0 else 0.0
            
            else: # Auto tag
                physical_tag_qualities[tag_name] = self.config.scene_quality_auto_tag_default_quality
        return physical_tag_qualities