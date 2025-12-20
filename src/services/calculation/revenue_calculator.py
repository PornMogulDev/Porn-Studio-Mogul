import numpy as np
from typing import Dict, List, Tuple

from data.game_state import MarketGroupState
from data.data_manager import DataManager
from services.models.configs import SceneCalculationConfig
from services.models.results import SceneRevenueResult
from services.models.inputs import RevenueInput, ContentTagInput

class RevenueCalculator:
    """
    Calculates the final revenue based on a standardized RevenueInput DTO.
    Purely stateless and decoupled from Scene/Talent entities.
    """
    def __init__(self, data_manager: DataManager, config: SceneCalculationConfig):
        """
        Initializes the RevenueCalculator.
        Args:
            data_manager: Provides access to game data, e.g., market definitions.
            config: Configuration DTO with calculation constants.
        """
        self.data_manager = data_manager
        self.config = config

    def calculate_revenue(
        self,
        input_data: RevenueInput,
        all_market_states: Dict[str, MarketGroupState],
        all_resolved_groups: Dict[str, Dict]
    ) -> SceneRevenueResult:
        """
        Calculates the final revenue for a scene and its market impact.
        This method iterates through all viewer groups, calculating each group's
        interest in the scene based on thematic tags, content tags (actions,
        physique), star power, and other factors. It then converts this
        interest into revenue, applies global penalties, and returns a
        structured result.
        Args:
            input_data: A DTO containing all necessary data about the scene.
            all_market_states: A dict of the current state of all market groups.
            all_resolved_groups: A dict of fully resolved market group data,
                                 including preferences.
        Returns:
            A SceneRevenueResult DTO with the total revenue, per-group interest,
            and market saturation changes.
        """
        viewer_group_interest = {}
        revenue_modifier_details = {}
        market_saturation_updates = {}
        total_revenue = 0
        base_revenue = self.config.base_release_revenue

        # Pre-calculate total weight for normalization across all groups
        total_tag_weight = sum(t.weight for t in input_data.content_tags)

        for group in self.data_manager.market_data.get('viewer_groups', []):
            group_name = group.get('name')
            if not group_name: continue

            resolved_group_data = all_resolved_groups.get(group_name, {})
            prefs = resolved_group_data.get('preferences', {})

            # 1. Calculate ADDITIVE Thematic Appeal
            additive_appeal = 0.0
            thematic_prefs = prefs.get('thematic_sentiments', {})
            for tag_name in input_data.global_tags:
                additive_appeal += thematic_prefs.get(tag_name, 0.0)

            # 2. Calculate MULTIPLICATIVE Content Appeal
            multiplicative_appeal = self._calculate_content_appeal(
                input_data.content_tags, prefs, total_tag_weight
            )

            # 3. Combine and Finalize Score
            group_interest_score = multiplicative_appeal + additive_appeal

            # Dom/Sub Preference
            ds_sentiments = prefs.get('dom_sub_sentiments', {})
            ds_multiplier = ds_sentiments.get(str(input_data.dom_sub_level), 1.0)
            group_interest_score *= ds_multiplier

            # Star Power Bonus
            avg_pop = input_data.star_power_scores.get(group_name, 0.0)
            star_power_bonus = 1.0 + (avg_pop * self.config.star_power_revenue_scalar)
            group_interest_score *= star_power_bonus

            if star_power_bonus > 1.0:
                revenue_modifier_details[f"Star Power ({group_name})"] = round(star_power_bonus, 2)

            # Focus Bonus
            if input_data.focus_target == group_name:
                group_interest_score *= resolved_group_data.get('focus_bonus', 1.0)

            viewer_group_interest[group_name] = round(group_interest_score, 4)

            # 4. Convert Interest to Revenue and Saturation Cost
            if group_interest_score > 0:
                dynamic_state = all_market_states.get(group_name)
                saturation = dynamic_state.current_saturation if dynamic_state else 1.0
                market_share = resolved_group_data.get('market_share_percent', 0) / 100.0
                spending_power = resolved_group_data.get('spending_power', 1.0)

                total_revenue += (base_revenue * market_share) * group_interest_score * spending_power # * saturation Don't know if we should keep this or not. While we balance AI studios, let's take it out.

                if dynamic_state:
                    saturation_cost = group_interest_score * self.config.saturation_spend_rate
                    market_saturation_updates[group_name] = saturation_cost

        # 5. Global Penalties
        final_penalty_multiplier, penalty_details = self._calculate_revenue_penalties(input_data)
        revenue_modifier_details.update(penalty_details)

        return SceneRevenueResult(
            total_revenue=int(total_revenue * final_penalty_multiplier),
            viewer_group_interest=viewer_group_interest,
            revenue_modifier_details=revenue_modifier_details,
            market_saturation_updates=market_saturation_updates
        )

    def _calculate_content_appeal(self, content_tags: List[ContentTagInput], prefs: Dict, total_tag_weight: float) -> float:
        """
        Calculates the weighted, normalized appeal from content tags.
        This score is a sum of individual tag contributions, where each
        contribution is its quality multiplied by viewer preference and its
        relative weight in the scene.
        """
        multiplicative_appeal = 0.0
        phys_prefs = prefs.get('physical_sentiments', {})
        act_prefs = prefs.get('action_sentiments', {})
        orient_prefs = prefs.get('orientation_sentiments', {})
        scaling_rules = prefs.get('scaling_sentiments', {})
        default_sentiment = self.config.default_sentiment_multiplier

        # Iterate through pre-weighted content tags
        for tag_input in content_tags:
            pref_multiplier = default_sentiment

            # Base Preference
            if tag_input.tag_type == 'Physical':
                pref_multiplier = phys_prefs.get(tag_input.tag_name, default_sentiment)
            elif tag_input.tag_type == 'Action':
                pref_multiplier = act_prefs.get(tag_input.tag_name, default_sentiment)

            # Orientation Preference
            if tag_input.orientation:
                pref_multiplier *= orient_prefs.get(tag_input.orientation, 1.0)

            # Scaling Rules (Diminishing returns or bonuses based on usage)
            rule = scaling_rules.get(tag_input.tag_name) or \
                   (scaling_rules.get(tag_input.concept) if tag_input.concept else None)

            if isinstance(rule, dict) and tag_input.scaling_params:
                pref_multiplier *= self._get_scaling_sentiment_multiplier(rule, tag_input)

            # Relative Weighted contribution: Quality * Preference * (Weight / TotalWeight)
            # This creates a normalized score where 1.0 Quality = Preference Multiplier
            relative_weight = tag_input.weight / total_tag_weight if total_tag_weight > 0 else 0
            multiplicative_appeal += (tag_input.quality * pref_multiplier * relative_weight)
        
        return multiplicative_appeal

    def _get_scaling_sentiment_multiplier(self, rule: Dict, tag_input: ContentTagInput) -> float:
        """
        Calculates a multiplier from a scaling sentiment rule.
        These rules can grant bonuses or penalties based on the number of
        performers in a certain role (e.g., 'Giver').
        """
        role_key = rule.get("based_on_role")
        count = tag_input.scaling_params.get(role_key, 0)
        bonus, penalty = 0.0, 0.0
        
        # Calculate bonus if the count exceeds the threshold
        if count > (applies_after := rule.get("applies_after", 0)):
            units = count - applies_after
            if "bonuses" in rule and rule["bonuses"]:
                # Sum from a list of diminishing bonuses, e.g., [0.2, 0.1, 0.05]
                # If units > len(bonuses), the last bonus value is used repeatedly.
                bonus = sum(rule["bonuses"][min(i, len(rule["bonuses"]) - 1)] for i in range(units))
            elif "bonus_per_unit" in rule: 
                bonus = units * rule["bonus_per_unit"]
                
        # Calculate penalty if the count exceeds the threshold
        if (penalty_after := rule.get("penalty_after")) is not None and count > penalty_after: 
            penalty = (count - penalty_after) * rule.get("penalty_per_unit", 0)
        
        return 1.0 + bonus - penalty

    def _calculate_revenue_penalties(self, input_data: RevenueInput) -> Tuple[float, Dict]:
        """
        Calculates global revenue penalties based on scene characteristics.
        Applies penalties for issues like being too short, monotonous, or
        having too many disparate tags ("overstuffed").
        Args:
            input_data: A DTO containing scene data like runtime and tags.
        Returns:
            A tuple containing the final penalty multiplier (e.g., 0.8) and a
            dictionary detailing the penalties applied.
        """
        penalty_config = self.config.revenue_penalties
        final_penalty_multiplier = 1.0
        penalty_details = {}
        
        runtime = input_data.total_runtime_minutes

        # Short Scene Penalty
        short_scene_config = penalty_config.get("short_scene", {})
        if short_scene_config.get("enabled", False) and runtime < (no_penalty_minutes := short_scene_config.get("no_penalty_minutes", 10)):
            max_penalty_minutes = short_scene_config.get("max_penalty_minutes", 1)
            max_penalty_mult = short_scene_config.get("max_penalty_multiplier", 0.30)
            short_scene_mult = np.interp(runtime, [max_penalty_minutes, no_penalty_minutes], [max_penalty_mult, 1.0])
            final_penalty_multiplier *= short_scene_mult
            penalty_details["Short Scene Penalty"] = round(short_scene_mult, 2)

        # Monotony Penalty (Requires Concept diversity)
        long_scene_config = penalty_config.get("long_monotonous_scene", {})
        if long_scene_config.get("enabled", False) and runtime > long_scene_config.get("min_runtime_minutes_for_penalty", 40):
            unique_concepts = {t.concept or t.tag_name for t in input_data.content_tags if t.tag_type == 'Action'}
            concepts_per_10_min = len(unique_concepts) / (runtime / 10.0)
            
            if concepts_per_10_min < (target_concepts := long_scene_config.get("target_concepts_per_10_min", 0.8)):
                max_penalty_mult = long_scene_config.get("max_penalty_multiplier", 0.65)
                monotony_mult = np.interp(concepts_per_10_min, [0, target_concepts], [max_penalty_mult, 1.0])
                final_penalty_multiplier *= monotony_mult
                penalty_details["Monotony Penalty"] = round(monotony_mult, 2)

        # Overstuffed Penalty (Too many tags per minute)
        overstuffed_config = penalty_config.get("overstuffed_scene", {})
        if overstuffed_config.get("enabled", False) and runtime >= overstuffed_config.get("min_runtime_minutes_for_penalty", 15):
            unique_concepts = {t.concept or t.tag_name for t in input_data.content_tags}
            tags_per_10_min = len(unique_concepts) / (runtime / 10.0)
            
            if tags_per_10_min > (threshold := overstuffed_config.get("penalty_threshold_tags_per_10_min", 3.0)):
                max_penalty_mult = overstuffed_config.get("max_penalty_multiplier", 0.75)
                max_density = overstuffed_config.get("max_penalty_tags_per_10_min", 6.0)
                clamped_density = min(tags_per_10_min, max_density)
                overstuffed_mult = np.interp(clamped_density, [threshold, max_density], [1.0, max_penalty_mult])
                final_penalty_multiplier *= overstuffed_mult
                penalty_details["Overstuffed Scene Penalty"] = round(overstuffed_mult, 2)

        return final_penalty_multiplier, penalty_details