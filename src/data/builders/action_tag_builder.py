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
            # If no expansions defined, return as is (or maybe it's not a template?)
            return [template_tag]

        for orientation in supported_orientations:
            new_tag = copy.deepcopy(template_tag)
            
            # 1. Set the concrete orientation
            new_tag['orientation'] = orientation
            
            # 2. Remove template-specific fields
            new_tag.pop('is_orientation_template', None)
            new_tag.pop('expands_to', None)
            # We KEEP 'is_template' because that flag is used by the UI to determine 
            # if the tag has editable parameters (like participant counts).
            
            # 3. Resolve "Dependent" genders in slots
            new_tag['slots'] = ActionTagBuilder._resolve_slots(new_tag.get('slots', []), orientation)
            
            expanded_tags.append(new_tag)
            
        return expanded_tags

    @staticmethod
    def _resolve_slots(slots: List[Dict[str, Any]], orientation: str) -> List[Dict[str, Any]]:
        """
        Resolves 'Dependent' gender slots based on the orientation and the 'Fixed' slot.
        """
        resolved_slots = copy.deepcopy(slots)
        
        # First, find the fixed gender if any (usually the one that isn't Dependent)
        # In most templates, one role is fixed (e.g. Receiver is Female in Straight/Lesbian)
        # But actually, for "Straight", one is Male and one is Female.
        # For "Gay", both Male. For "Lesbian", both Female.
        # For "Bi", usually one is Any or specific.
        
        # Let's look at the logic required.
        # If orientation is "Straight": One Male, One Female.
        # If orientation is "Gay": Both Male.
        # If orientation is "Lesbian": Both Female.
        # If orientation is "Bi": Usually one Fixed, one Any.
        
        # We need to know WHICH role takes which gender.
        # The template should probably define the logic or we infer it.
        # In the plan, we said we'd mark one as "Dependent".
        
        # Let's assume the template has one slot with a concrete gender (or Any) 
        # and one slot with "Dependent".
        
        # Actually, looking at the previous `action_tags.json`:
        # Blowjob (Straight): Receiver (Male), Giver (Female)
        # Blowjob (Gay): Receiver (Male), Giver (Male)
        # Blowjob (Lesbian): Receiver (Female), Giver (Female) -- Wait, Blowjob Lesbian? 
        # Ah, "Blowjob (Strapon)" exists for Lesbian.
        # "Deepthroat" (Straight): Receiver (Male), Giver (Female)
        
        # It seems "Dependent" usually means "Matches the other person" (Gay/Lesbian) 
        # or "Opposite of the other person" (Straight).
        
        # Let's refine the logic.
        # If we have a "Dependent" slot, we need to know what it depends ON.
        # Or we can just hardcode the logic based on standard orientation rules if the template is simple.
        
        # However, a more robust way is to define the mapping in the builder.
        
        for slot in resolved_slots:
            if slot.get('gender') == 'Dependent':
                slot['gender'] = ActionTagBuilder._calculate_dependent_gender(orientation, resolved_slots, slot)
                
        return resolved_slots

    @staticmethod
    def _calculate_dependent_gender(orientation: str, all_slots: List[Dict], current_slot: Dict) -> str:
        # This is a bit tricky without more metadata.
        # Let's look at "Blowjob". 
        # Template: Receiver (Male), Giver (Dependent).
        # Straight -> Giver = Female.
        # Gay -> Giver = Male.
        # Bi -> Giver = Any.
        
        # Template: "Vaginal".
        # Straight: Receiver (Female), Giver (Male).
        # Lesbian: Receiver (Female), Giver (Female).
        # Bi: Receiver (Female), Giver (Any).
        
        # It seems "Dependent" maps to:
        # Straight -> Opposite of the *other* slot? Or just fixed mapping?
        # Actually, it's easier to map Orientation -> Gender Set.
        
        # Straight: [Male, Female]
        # Gay: [Male, Male]
        # Lesbian: [Female, Female]
        # Bi: [Any, Any] (or [Fixed, Any])
        
        # If the template has a Fixed slot (e.g. Receiver=Male for Blowjob), 
        # then the Dependent slot takes the remaining gender from the pair?
        
        # Let's try a simpler approach:
        # The template defines the "Primary" gender (e.g. Receiver).
        # The "Dependent" slot changes based on orientation.
        
        if orientation == "Straight":
            # If there's a Male slot, the Dependent is Female.
            # If there's a Female slot, the Dependent is Male.
            # If there's a Fixed slot, we take the opposite.
            other_gender = ActionTagBuilder._get_other_fixed_gender(all_slots, current_slot)
            if other_gender == "Male": return "Female"
            if other_gender == "Female": return "Male"
            return "Any" # Fallback
            
        elif orientation == "Gay":
            return "Male"
            
        elif orientation == "Lesbian":
            return "Female"
            
        elif orientation == "Bi":
            return "Any"
            
        return "Any"

    @staticmethod
    def _get_other_fixed_gender(slots: List[Dict], current_slot: Dict) -> str:
        for slot in slots:
            if slot is current_slot: continue
            g = slot.get('gender')
            if g in ["Male", "Female"]:
                return g
        return "Any"
