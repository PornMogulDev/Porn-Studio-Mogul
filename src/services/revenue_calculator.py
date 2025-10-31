import numpy as np
from typing import Dict, List, Tuple

from data.game_state import Scene, Talent, MarketGroupState
from data.data_manager import DataManager
from services.service_config import SceneCalculationConfig
from services.calculation_models import SceneRevenueResult

class RevenueCalculator:
    """
    Calculates the final revenue for a released scene, including market
    interest and penalties.
    """
    def __init__(self, data_manager: DataManager, config: SceneCalculationConfig):
        self.data_manager = data_manager
        self.config = config

    def calculate_revenue(
        self, scene: Scene, cast_talents: List[Talent], 
        all_market_states: Dict[str, MarketGroupState],
        all_resolved_groups: Dict[str, Dict]
    ) -> SceneRevenueResult:
        """
        Calculates scene revenue and market saturation impact.
        
        Args:
            scene: The Scene dataclass being released.
            cast_talents: The cast of the scene.
            all_market_states: Current saturation state of all market groups.
            all_resolved_groups: Fully resolved preference data for all groups.

        Returns:
            A SceneRevenueResult object with all calculation outcomes.
        """
        viewer_group_interest = {}
        revenue_modifier_details = {}
        market_saturation_updates = {}
        total_revenue = 0
        base_revenue = self.config.base_release_revenue

        all_tags_with_weights = self._calculate_tag_weights(scene)

        for group in self.data_manager.market_data.get('viewer_groups', []):
            group_name = group.get('name')
            if not group_name: continue
            
            resolved_group_data = all_resolved_groups.get(group_name, {})
            prefs = resolved_group_data.get('preferences', {})
            
            # ... [ The entire group interest calculation logic from the original method ] ...
            # 1. Calculate ADDITIVE Thematic Appeal
            additive_appeal = 0.0
            thematic_prefs = prefs.get('thematic_sentiments', {})
            for tag_name in scene.global_tags: additive_appeal += thematic_prefs.get(tag_name, 0.0)
            # 2. Calculate MULTIPLICATIVE Content Appeal
            multiplicative_appeal = 0.0
            phys_prefs = prefs.get('physical_sentiments', {}); act_prefs = prefs.get('action_sentiments', {}); orient_prefs = prefs.get('orientation_sentiments', {}); scaling_rules = prefs.get('scaling_sentiments', {})
            default_sentiment = self.config.default_sentiment_multiplier
            action_segments_for_calc = scene.get_expanded_action_segments(self.data_manager.tag_definitions)
            for tag_key, weight in all_tags_with_weights.items():
                full_tag_name = tag_key.split('_')[0]
                tag_def = self.data_manager.tag_definitions.get(full_tag_name, {}); tag_type = tag_def.get('type')
                if tag_type == 'Thematic': continue
                quality = scene.tag_qualities.get(full_tag_name, 100.0) / 100.0
                pref_multiplier = default_sentiment
                if tag_type == 'Physical': pref_multiplier = phys_prefs.get(full_tag_name, default_sentiment)
                elif tag_type == 'Action': pref_multiplier = act_prefs.get(full_tag_name, default_sentiment)
                if orientation := tag_def.get('orientation'): pref_multiplier *= orient_prefs.get(orientation, 1.0)
                if segment := next((s for s in action_segments_for_calc if f"{s.tag_name}_{s.id}" == tag_key), None):
                    base_name, concept = tag_def.get('name'), tag_def.get('concept')
                    rule = scaling_rules.get(full_tag_name) or (scaling_rules.get(base_name) if base_name else None) or (scaling_rules.get(concept) if concept else None)
                    if isinstance(rule, dict):
                        count = segment.parameters.get(rule.get("based_on_role"), 0); bonus, penalty = 0.0, 0.0
                        if count > (applies_after := rule.get("applies_after", 0)):
                            units = count - applies_after
                            if "bonuses" in rule: bonus = sum(rule["bonuses"][min(i, len(rule["bonuses"]) - 1)] for i in range(units))
                            elif "bonus_per_unit" in rule: bonus = units * rule["bonus_per_unit"]
                        if (penalty_after := rule.get("penalty_after")) is not None and count > penalty_after: penalty = (count - penalty_after) * rule.get("penalty_per_unit", 0)
                        pref_multiplier *= (1.0 + bonus - penalty)
                multiplicative_appeal += (quality * pref_multiplier * weight)
            # 3. Combine and Finalize Score
            group_interest_score = multiplicative_appeal + additive_appeal
            ds_sentiments = prefs.get('dom_sub_sentiments', {}); ds_multiplier = ds_sentiments.get(str(scene.dom_sub_dynamic_level), 1.0)
            group_interest_score *= ds_multiplier
            if cast_talents:
                avg_pop = np.mean([t.popularity.get(group_name, 0.0) for t in cast_talents]); star_power_bonus = 1.0 + (avg_pop * self.config.star_power_revenue_scalar)
                group_interest_score *= star_power_bonus
                if star_power_bonus > 1.0: revenue_modifier_details[f"Star Power ({group_name})"] = round(star_power_bonus, 2)
            if scene.focus_target == group_name: group_interest_score *= resolved_group_data.get('focus_bonus', 1.0)
            
            viewer_group_interest[group_name] = round(group_interest_score, 4)

            if group_interest_score > 0:
                dynamic_state = all_market_states.get(group_name)
                saturation = dynamic_state.current_saturation if dynamic_state else 1.0
                market_share = resolved_group_data.get('market_share_percent', 0) / 100.0
                spending_power = resolved_group_data.get('spending_power', 1.0)
                total_revenue += (base_revenue * market_share) * group_interest_score * spending_power * saturation
                if dynamic_state:
                    saturation_cost = group_interest_score * self.config.saturation_spend_rate
                    market_saturation_updates[group_name] = saturation_cost

        final_penalty_multiplier, penalty_details = self._calculate_revenue_penalties(scene)
        revenue_modifier_details.update(penalty_details)
        
        return SceneRevenueResult(
            total_revenue=int(total_revenue * final_penalty_multiplier),
            viewer_group_interest=viewer_group_interest,
            revenue_modifier_details=revenue_modifier_details,
            market_saturation_updates=market_saturation_updates
        )

    def _calculate_tag_weights(self, scene: Scene) -> Dict:
        """Helper to calculate the relative weight of each tag for revenue."""
        # ... [ Code from original calculate_revenue ] ...
        all_tags_with_weights = {}; focused_weight = self.config.revenue_weight_focused_physical_tag
        for tag_name in scene.assigned_tags:
            tag_def = self.data_manager.tag_definitions.get(tag_name, {})
            all_tags_with_weights[tag_name] = tag_def.get('revenue_weights', {}).get('focused', focused_weight)
        default_action_weight = self.config.revenue_weight_default_action_appeal
        action_segments_for_calc = scene.get_expanded_action_segments(self.data_manager.tag_definitions)
        for segment in action_segments_for_calc:
            unique_key = f"{segment.tag_name}_{segment.id}"; tag_def = self.data_manager.tag_definitions.get(segment.tag_name, {})
            appeal_weight = tag_def.get('appeal_weight') or default_action_weight
            all_tags_with_weights[unique_key] = (segment.runtime_percentage / 100.0) * appeal_weight
        auto_weight = self.config.revenue_weight_auto_tag; focused_tags = set(scene.global_tags) | set(scene.assigned_tags.keys())
        for tag_name in scene.auto_tags:
            if tag_name not in focused_tags:
                tag_def = self.data_manager.tag_definitions.get(tag_name, {})
                all_tags_with_weights[tag_name] = tag_def.get('revenue_weights', {}).get('auto', auto_weight)
        if total_weight := sum(all_tags_with_weights.values()):
            return {k: v / total_weight for k, v in all_tags_with_weights.items()}
        return {}

    def _calculate_revenue_penalties(self, scene: Scene) -> Tuple[float, Dict]:
        """Helper to calculate all revenue penalties for a scene."""
        # ... [ Code for penalty logic from original calculate_revenue ] ...
        penalty_config = self.config.revenue_penalties; final_penalty_multiplier = 1.0; penalty_details = {}
        short_scene_config = penalty_config.get("short_scene", {})
        if short_scene_config.get("enabled", False) and scene.total_runtime_minutes < (no_penalty_minutes := short_scene_config.get("no_penalty_minutes", 10)):
            max_penalty_minutes = short_scene_config.get("max_penalty_minutes", 1); max_penalty_mult = short_scene_config.get("max_penalty_multiplier", 0.30)
            short_scene_mult = np.interp(scene.total_runtime_minutes, [max_penalty_minutes, no_penalty_minutes], [max_penalty_mult, 1.0])
            final_penalty_multiplier *= short_scene_mult; penalty_details["Short Scene Penalty"] = round(short_scene_mult, 2)
        long_scene_config = penalty_config.get("long_monotonous_scene", {})
        if long_scene_config.get("enabled", False) and scene.total_runtime_minutes > long_scene_config.get("min_runtime_minutes_for_penalty", 40):
            unique_concepts = {self.data_manager.tag_definitions.get(s.tag_name, {}).get('concept', s.tag_name) for s in scene.get_expanded_action_segments(self.data_manager.tag_definitions)}
            concepts_per_10_min = len(unique_concepts) / (scene.total_runtime_minutes / 10.0)
            if concepts_per_10_min < (target_concepts := long_scene_config.get("target_concepts_per_10_min", 0.8)):
                max_penalty_mult = long_scene_config.get("max_penalty_multiplier", 0.65)
                monotony_mult = np.interp(concepts_per_10_min, [0, target_concepts], [max_penalty_mult, 1.0])
                final_penalty_multiplier *= monotony_mult; penalty_details["Monotony Penalty"] = round(monotony_mult, 2)
        overstuffed_config = penalty_config.get("overstuffed_scene", {})
        if overstuffed_config.get("enabled", False) and scene.total_runtime_minutes >= overstuffed_config.get("min_runtime_minutes_for_penalty", 15):
            all_tags = set(scene.global_tags) | set(scene.assigned_tags.keys()) | {s.tag_name for s in scene.get_expanded_action_segments(self.data_manager.tag_definitions)}
            unique_concepts = {self.data_manager.tag_definitions.get(t, {}).get('concept', t) for t in all_tags}
            tags_per_10_min = len(unique_concepts) / (scene.total_runtime_minutes / 10.0)
            if tags_per_10_min > (threshold := overstuffed_config.get("penalty_threshold_tags_per_10_min", 3.0)):
                max_penalty_mult = overstuffed_config.get("max_penalty_multiplier", 0.75); max_density = overstuffed_config.get("max_penalty_tags_per_10_min", 6.0)
                clamped_density = min(tags_per_10_min, max_density); overstuffed_mult = np.interp(clamped_density, [threshold, max_density], [1.0, max_penalty_mult])
                final_penalty_multiplier *= overstuffed_mult; penalty_details["Overstuffed Scene Penalty"] = round(overstuffed_mult, 2)
        return final_penalty_multiplier, penalty_details