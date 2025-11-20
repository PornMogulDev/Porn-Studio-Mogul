from typing import List, Dict, Any
import copy

class ActionTagBuilder:
    """
    Expands action tag templates into concrete orientation-specific tags.
    """

    @staticmethod
    def expand_template(template_tag: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Takes a template tag definition and returns a list of concrete tag definitions
        for each supported orientation.
        """
        expanded_tags = []
        supported_orientations = template_tag.get('expands_to', [])
        
        if not supported_orientations:
            # Fallback: If marked as template but has no expansions, return as is.
            return [template_tag]

        for orientation in supported_orientations:
            new_tag = copy.deepcopy(template_tag)
            
            # 1. Set the concrete orientation
            new_tag['orientation'] = orientation
            
            # 2. Remove template-specific metadata to keep the final tag clean
            new_tag.pop('is_orientation_template', None)
            new_tag.pop('expands_to', None)
            
            # Note: We KEEP 'is_template' because that flag is used by the UI 
            # to determine if the tag has editable parameters (spinners).
            
            # 3. Resolve "Dependent" and "Any" genders in slots
            new_tag['slots'] = ActionTagBuilder._resolve_slots(new_tag.get('slots', []), orientation)
            
            # 4. Update name for internal uniqueness if needed, though usually
            # the combination of Name + Orientation is the unique key in the app.
            # (The DataManager keys it by "Name (Orientation)")
            
            expanded_tags.append(new_tag)
            
        return expanded_tags

    @staticmethod
    def _resolve_slots(slots: List[Dict[str, Any]], orientation: str) -> List[Dict[str, Any]]:
        """
        Resolves 'Dependent' and 'Any' gender slots based on the orientation.
        """
        resolved_slots = copy.deepcopy(slots)
        
        for slot in resolved_slots:
            gender = slot.get('gender')
            
            if gender == 'Dependent':
                slot['gender'] = ActionTagBuilder._calculate_dependent_gender(orientation, resolved_slots, slot)
            elif gender == 'Any':
                slot['gender'] = ActionTagBuilder._refine_any_gender(orientation)
                
        return resolved_slots

    @staticmethod
    def _calculate_dependent_gender(orientation: str, all_slots: List[Dict], current_slot: Dict) -> str:
        """
        Determines what 'Dependent' means based on the orientation and context of other slots.
        """
        # Case 1: Homosexual / Mono-gender orientations
        if orientation in ["Gay", "Male"]:
            return "Male"
        if orientation in ["Lesbian", "Female"]:
            return "Female"
            
        # Case 2: Bi / Pan
        if orientation == "Bi":
            return "Any"

        # Case 3: Straight
        if orientation == "Straight":
            # Logic: Find the 'Fixed' gender in the OTHER slots. 
            # If the other slot is Male, this one is Female, and vice versa.
            other_gender = ActionTagBuilder._find_other_fixed_gender(all_slots, current_slot)
            
            if other_gender == "Male": 
                return "Female"
            if other_gender == "Female": 
                return "Male"
            
            # Fallback: If Straight but the other slot is Any (Fluid Straight), return Any.
            return "Any"
            
        return "Any"

    @staticmethod
    def _refine_any_gender(orientation: str) -> str:
        """
        Refines 'Any' gender for specific orientations.
        e.g., In a Gay tag, 'Any' implicitly means 'Male'.
        In a Straight tag, 'Any' stays 'Any' (Fluid roles).
        """
        if orientation in ["Gay", "Male"]:
            return "Male"
        if orientation in ["Lesbian", "Female"]:
            return "Female"
        
        # For Straight and Bi, 'Any' remains 'Any' to allow flexible/fluid positioning.
        return "Any"

    @staticmethod
    def _find_other_fixed_gender(slots: List[Dict], current_slot: Dict) -> str:
        """Helper to find a defined gender (Male/Female) in a different slot."""
        for slot in slots:
            if slot is current_slot: 
                continue
            g = slot.get('gender')
            if g in ["Male", "Female"]:
                return g
        return "Any"