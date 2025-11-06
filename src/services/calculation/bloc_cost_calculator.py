from typing import Dict, List

from data.data_manager import DataManager

class BlocCostCalculator:
    def __init__(self, data_manager: DataManager):
         self.data_manager = data_manager

    def calculate_shooting_bloc_cost(self, num_scenes: int, settings: Dict[str, str], policies: List[str]) -> int:
            """Calculates the authoritative cost for creating a shooting bloc."""
            total_cost_per_scene = 0

            # Special handling for Camera cost
            cam_equip_tier_name = settings.get("Camera Equipment")
            cam_setup_tier_name = settings.get("Camera Setup")
            
            equip_cost = 0
            if cam_equip_tier_name:
                tiers = self.data_manager.production_settings_data.get("Camera Equipment", [])
                tier_info = next((t for t in tiers if t['tier_name'] == cam_equip_tier_name), None)
                if tier_info:
                    equip_cost = tier_info.get('cost_per_scene', 0)

            setup_multiplier = 1.0
            if cam_setup_tier_name:
                tiers = self.data_manager.production_settings_data.get("Camera Setup", [])
                tier_info = next((t for t in tiers if t['tier_name'] == cam_setup_tier_name), None)
                if tier_info:
                    setup_multiplier = tier_info.get('cost_multiplier', 1.0)
            
            total_cost_per_scene += equip_cost * setup_multiplier

            # Add costs from all other standard categories
            for category, tier_name in settings.items():
                if category in ["Camera Equipment", "Camera Setup"]: continue
                tiers = self.data_manager.production_settings_data.get(category, [])
                tier_info = next((t for t in tiers if t['tier_name'] == tier_name), None)
                if tier_info:
                    total_cost_per_scene += tier_info.get('cost_per_scene', 0)
            settings_cost = total_cost_per_scene * num_scenes

            policies_cost = sum(self.data_manager.on_set_policies_data.get(p_id, {}).get('cost_per_bloc', 0) for p_id in policies)
            
            return int(settings_cost + policies_cost)