from data.game_state import ActionSegment

class RolePerformanceService:
    """
    A pure calculation service that determines modifiers for a talent's role
    based on the context of a scene segment (e.g., number of partners).
    This logic is used for calculating both hiring demand and stamina cost.
    """
    @staticmethod
    def get_final_modifier(base_modifier_key: str, slot_def: dict, segment: ActionSegment, role: str) -> float:
        """
        Calculates the final modifier for a given attribute (demand, stamina)
        based on scaling rules for the number of peers and other participants.

        Args:
            base_modifier_key: The key for the base modifier (e.g., 'demand_modifier').
            slot_def: The definition dictionary for the specific slot.
            segment: The ActionSegment being analyzed.
            role: The role the talent is performing ('Giver', 'Receiver', etc.).

        Returns:
            The final calculated modifier.
        """
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