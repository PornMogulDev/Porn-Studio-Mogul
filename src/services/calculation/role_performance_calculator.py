from typing import Dict, Optional, Tuple
from data.game_state import ActionSegment, Scene

class RolePerformanceCalculator:
    """
    A pure calculation service that determines modifiers for a talent's role
    based on the context of a scene segment (e.g., number of partners).
    This logic is used for calculating hiring demand, stamina cost, and other role-based effects.
    """
    def _get_role_context_for_vp(self, segment: ActionSegment, vp_id: int, scene: Scene, tag_definitions: Dict) -> Optional[Tuple[str, Dict]]:
        """
        Finds the role and slot definition for a specific virtual performer in a segment.

        This method relies on the `slot_id` having a specific format:
        '<Tag Name>_<Role Name>_<Index>', e.g., 'Blowjob (Straight)_Giver_1'.
        It parses this string to extract the 'Role Name' and validates it against the
        possible roles defined in the tag.

        Args:
            segment: The action segment being analyzed.
            vp_id: The ID of the virtual performer whose role we need to find.
            scene: The parent scene object.
            tag_definitions: A dictionary of all tag definitions.

        Returns:
            A tuple containing the role name (str) and the slot definition (dict),
            or None if not found.
        """
        assignment = next((a for a in segment.slot_assignments if a.virtual_performer_id == vp_id), None)
        if not assignment:
            return None

        # Get the tag definition to find possible roles for validation
        tag_def = tag_definitions.get(segment.tag_name)
        if not tag_def:
            return None
        
        possible_roles = {s['role'] for s in tag_def.get('slots', [])}
        
        try:
            # Assumes format "TagName_RoleName_Index"
            _, role, _ = assignment.slot_id.rsplit('_', 2)
            
            # Validate that the parsed role is valid for this tag
            if role not in possible_roles:
                return None

        except ValueError:
            # slot_id does not conform to the expected format
            return None

        slots = scene._get_slots_for_segment(segment, tag_definitions)
        slot_def = next((s for s in slots if s['role'] == role), None)

        if not slot_def:
            return None
            
        return role, slot_def

    def get_role_stamina_modifier(self, segment: ActionSegment, vp_id: int, scene: Scene, tag_definitions: dict) -> float:
        """
        Calculates the final stamina modifier for a virtual performer in a given segment.

        Args:
            segment: The action segment being analyzed.
            vp_id: The ID of the virtual performer.
            scene: The parent scene object.
            tag_definitions: A dictionary of all tag definitions.

        Returns:
            The final calculated stamina modifier as a float. Defaults to 1.0.
        """
        context = self._get_role_context_for_vp(segment, vp_id, scene, tag_definitions)
        if not context:
            return 1.0 # Default modifier if role context can't be found
        
        role, slot_def = context
        return self._calculate_final_modifier('stamina_modifier', slot_def, segment, role)

    def get_role_demand_modifier(self, segment: ActionSegment, vp_id: int, scene: Scene, tag_definitions: dict) -> float:
        """
        Calculates the final hiring demand modifier for a virtual performer in a given segment.

        Args:
            segment: The action segment being analyzed.
            vp_id: The ID of the virtual performer.
            scene: The parent scene object.
            tag_definitions: A dictionary of all tag definitions.

        Returns:
            The final calculated demand modifier as a float. Defaults to 1.0.
        """
        context = self._get_role_context_for_vp(segment, vp_id, scene, tag_definitions)
        if not context:
            return 1.0

        role, slot_def = context
        return self._calculate_final_modifier('demand_modifier', slot_def, segment, role)

    def _calculate_final_modifier(self, base_modifier_key: str, slot_def: dict, segment: ActionSegment, role: str) -> float:
        """
        Calculates the final modifier for an attribute (demand, stamina) based on
        scaling rules for the number of peers and other participants in the segment.

        - "Peers" are other performers in the *same* role (e.g., other 'Giver's).
        - "Others" are performers in the *opposite* role (e.g., 'Receiver's).

        Args:
            base_modifier_key: The base key for the modifier (e.g., 'stamina_modifier').
            slot_def: The slot definition dictionary from the tag definition.
            segment: The action segment containing participant counts in its parameters.
            role: The specific role of the performer being calculated (e.g., 'Giver').

        Returns:
            The final calculated modifier as a float.
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