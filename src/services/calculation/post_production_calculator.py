from typing import Dict, List, Tuple

from data.data_manager import DataManager
from services.models.results import PostProductionResult

class PostProductionCalculator:
    """
    Calculates the effects of post-production choices on a scene's quality.
    """
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager

    def apply_effects(
        self, current_tag_qualities: Dict, 
        current_contributions: List[Dict],
        post_prod_choices: Dict, 
        bloc_production_settings: Dict,
        default_camera_tier: str
    ) -> PostProductionResult | None:
        """
        Calculates quality modifiers from post-production choices.

        Returns:
            A PostProductionResult object, or None if no effects were applied.
        """
        editing_tier_id = (post_prod_choices or {}).get('editing_tier')
        if not editing_tier_id:
            return None

        editing_options = self.data_manager.post_production_data.get('editing_tiers', [])
        tier_data = next((t for t in editing_options if t['id'] == editing_tier_id), None)
        if not tier_data:
            return None
            
        final_modifier = tier_data.get('base_quality_modifier', 1.0)
        camera_setup_tier = (bloc_production_settings or {}).get('Camera Setup', default_camera_tier)

        synergy_mod = tier_data.get('synergy_mods', {}).get(camera_setup_tier, 0.0)
        final_modifier += synergy_mod

        new_tag_qualities = current_tag_qualities.copy()
        if current_tag_qualities:
            for tag, quality in new_tag_qualities.items():
                new_tag_qualities[tag] = round(quality * final_modifier, 2)
        
        new_contributions = [c.copy() for c in current_contributions]
        for contrib in new_contributions:
             contrib['quality_score'] = round(contrib.get('quality_score', 0) * final_modifier, 2)
        
        revenue_mod_details = {
            f"Editing ({tier_data.get('name')})": round(final_modifier, 2)
        }
        
        return PostProductionResult(
            new_tag_qualities=new_tag_qualities,
            new_performer_contributions=new_contributions,
            revenue_modifier_details=revenue_mod_details
        )