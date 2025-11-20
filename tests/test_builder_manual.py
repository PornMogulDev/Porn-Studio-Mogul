import sys
import os
import json

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from data.builders.action_tag_builder import ActionTagBuilder

def test_builder():
    # Mock Template: Blowjob
    # Receiver is Fixed (Male), Giver is Dependent
    template = {
        "name": "Blowjob",
        "orientation": "Template",
        "is_orientation_template": True,
        "is_template": True, # UI flag
        "expands_to": ["Straight", "Gay", "Bi"],
        "slots": [
            {"role": "Receiver", "gender": "Male"},
            {"role": "Giver", "gender": "Dependent"}
        ]
    }
    
    print("Expanding Blowjob Template...")
    expanded = ActionTagBuilder.expand_template(template)
    
    for tag in expanded:
        print(f"Orientation: {tag['orientation']}")
        for slot in tag['slots']:
            print(f"  {slot['role']}: {slot['gender']}")
        print("-" * 20)

    # Mock Template: Vaginal
    # Receiver is Fixed (Female), Giver is Dependent
    template_vag = {
        "name": "Vaginal",
        "orientation": "Template",
        "is_orientation_template": True,
        "expands_to": ["Straight", "Lesbian", "Bi"], # Note: Vaginal Lesbian? (Tribbing/Strap?)
        # In original JSON: Vaginal Lesbian existed (Tribbing probably, or Strap)
        # Original Vaginal Lesbian: Receiver Female, Giver Female.
        "slots": [
            {"role": "Receiver", "gender": "Female"},
            {"role": "Giver", "gender": "Dependent"}
        ]
    }
    
    print("\nExpanding Vaginal Template...")
    expanded_vag = ActionTagBuilder.expand_template(template_vag)
    for tag in expanded_vag:
        print(f"Orientation: {tag['orientation']}")
        for slot in tag['slots']:
            print(f"  {slot['role']}: {slot['gender']}")
        print("-" * 20)

if __name__ == "__main__":
    test_builder()
