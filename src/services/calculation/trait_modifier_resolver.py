import logging
from typing import Union
from services.models.constants import TraitModifiers 

from data.data_manager import DataManager
from data.game_state import Talent

logger = logging.getLogger(__name__)

class TraitModifierResolver:
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager

    def get_composite_modifier(self, talent: Talent, modifier_key: Union[str, TraitModifiers], 
                               default_value: float = 1.0, operation: str = 'multiply') -> float:
        
        # Allow passing Enum, convert to string value automatically
        key_str = modifier_key.value if isinstance(modifier_key, TraitModifiers) else modifier_key

        if not talent.traits:
            return default_value

        current_value = default_value

        for trait_id in talent.traits:
            # Supports both standard traits and archetypes
            trait_def = self.data_manager.get_trait_definition(trait_id)
            if not trait_def: continue

            modifiers = trait_def.get('modifiers', {})
            
            # Use the string key to look up the value in the JSON data
            if key_str in modifiers:
                mod_value = modifiers[key_str]
                
                if operation == 'multiply':
                    current_value *= mod_value
                elif operation == 'add':
                    current_value += mod_value
        
        return current_value

    def resolve_stress_modifiers(self, talent: Talent, location_def: dict, active_policies: list[str], cast_size: int) -> float:
        """
        Calculates total stress modifier from a talent's traits based on context.
        """
        total_stress_mod = 0.0
        if not talent.traits:
            return total_stress_mod

        for trait_id in talent.traits:
            trait_def = self.data_manager.get_trait_definition(trait_id)
            if not trait_def: continue
            
            stress_mods = trait_def.get('stress_modifiers')
            if not stress_mods: continue

            # 1. Location tag penalties
            location_tags = location_def.get('tags', [])
            tag_penalties = stress_mods.get('location_tag_penalties', {})
            for tag, penalty in tag_penalties.items():
                if tag in location_tags:
                    total_stress_mod += penalty

            # 2. Policy penalties
            policy_penalties = stress_mods.get('policy_penalties', {})
            for policy_id, penalty in policy_penalties.items():
                if policy_id in active_policies:
                    total_stress_mod += penalty
            
            # 3. Cast size penalty
            cast_size_scalar = stress_mods.get('cast_size_penalty_scalar', 0)
            if cast_size_scalar > 0:
                total_stress_mod += cast_size * cast_size_scalar

        return total_stress_mod