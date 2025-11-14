from typing import Dict, Optional, Tuple
from data.game_state import ActionSegment, Scene

class RolePerformanceCalculator:
    """
    A pure calculation service that determines modifiers for a talent's role
    based on the context of a scene segment (e.g., number of partners).
    This logic is used for calculating hiring demand, stamina cost, and other role-based effects.
    """
    def _get_role_context_for_vp(self, segment: ActionSegment, vp_id: int, scene: Scene, tag_definitions: Dict) -> Optional[Tuple[str, Dict]]:
        """Finds the role and slot definition for a specific virtual performer within a segment."""
        assignment = next((a for a in segment.slot_assignments if a.virtual_performer_id == vp_id), None)
        if not assignment:
            return None
        
        try:
            _, role, _ = assignment.slot_id.rsplit('_', 2)
        except ValueError:
            return None

        slots = scene._get_slots_for_segment(segment, tag_definitions)
        slot_def = next((s for s in slots if s['role'] == role), None)

        if not slot_def:
            return None
            
        return role, slot_def

    def get_role_stamina_modifier(self, segment: ActionSegment, vp_id: int, scene: Scene, tag_definitions: dict) -> float:
        """Calculates the final stamina modifier for a VP in a given segment."""
        context = self._get_role_context_for_vp(segment, vp_id, scene, tag_definitions)
        if not context:
            return 1.0 # Default modifier if role context can't be found
        
        role, slot_def = context
        return self._calculate_final_modifier('stamina_modifier', slot_def, segment, role)

    def get_role_demand_modifier(self, segment: ActionSegment, vp_id: int, scene: Scene, tag_definitions: dict) -> float:
        """Calculates the final hiring demand modifier for a VP in a given segment."""
        context = self._get_role_context_for_vp(segment, vp_id, scene, tag_definitions)
        if not context:
            return 1.0

        role, slot_def = context
        return self._calculate_final_modifier('demand_modifier', slot_def, segment, role)

    def _calculate_final_modifier(self, base_modifier_key: str, slot_def: dict, segment: ActionSegment, role: str) -> float:
        """
        Calculates the final modifier for a given attribute (demand, stamina)
        based on scaling rules for the number of peers and other participants.
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