import logging
from typing import Union

from data.data_manager import DataManager
from data.game_state import Talent

logger = logging.getLogger(__name__)

class TraitModifierResolver:
    """
    A stateless service responsible for calculating the composite effect of a 
    talent's traits on specific game variables (e.g., travel costs, salary demands).
    """
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager

    def get_composite_modifier(self, talent: Talent, modifier_key: str, 
                               default_value: float = 1.0, operation: str = 'multiply') -> float:
        """
        Iterates through a talent's traits and aggregates the value of a specific 
        modifier key defined in the traits JSON.

        Args:
            talent: The talent to inspect.
            modifier_key: The key to look for in trait['modifiers'] (e.g., 'travel_cost_multiplier').
            default_value: The starting value before modifiers are applied.
            operation: 'multiply' for percentage-based stacking, 'add' for flat bonuses.

        Returns:
            The final calculated value.
        """
        if not talent.traits:
            return default_value

        current_value = default_value

        for trait_id in talent.traits:
            # Support looking up standard traits OR archetypes (if treating archetypes as traits)
            trait_def = self.data_manager.get_trait_definition(trait_id)
            
            if not trait_def:
                continue

            modifiers = trait_def.get('modifiers', {})
            if modifier_key in modifiers:
                mod_value = modifiers[modifier_key]
                
                if operation == 'multiply':
                    current_value *= mod_value
                elif operation == 'add':
                    current_value += mod_value
        
        return current_value

    def has_trait_type(self, talent: Talent, trait_type: str) -> bool:
        """Checks if the talent has any trait of a specific type (e.g., 'behavioral')."""
        for trait_id in talent.traits:
            trait_def = self.data_manager.get_trait_definition(trait_id)
            if trait_def and trait_def.get('type') == trait_type:
                return True
        return False