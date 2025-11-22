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