#!/usr/bin/env python3
"""
Script to fix double-encoded UTF-8 strings in text data.
Handles common encoding issues from web scraping.
"""

import json
import sys
from typing import Any, Union


def fix_double_encoding(text: str) -> str:
    """
    Fix double or triple-encoded UTF-8 strings.
    
    Args:
        text: String with potential encoding issues
        
    Returns:
        Properly decoded string
    """
    if not isinstance(text, str):
        return text
    
    original = text
    
    # Try up to 3 levels of decoding
    for _ in range(3):
        try:
            decoded = text.encode('latin-1').decode('utf-8')
            # If decoding succeeded and changed the string, try again
            if decoded != text:
                text = decoded
            else:
                break
        except (UnicodeDecodeError, UnicodeEncodeError):
            # Can't decode further, return what we have
            break
    
    # Return the most decoded version, or original if nothing worked
    return text if text != original else original


def fix_data_structure(data: Any) -> Any:
    """
    Recursively fix encoding issues in nested data structures.
    
    Args:
        data: Can be dict, list, str, or other types
        
    Returns:
        Data structure with fixed strings
    """
    if isinstance(data, str):
        return fix_double_encoding(data)
    elif isinstance(data, dict):
        return {key: fix_data_structure(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [fix_data_structure(item) for item in data]
    else:
        return data


def process_json_file(input_file: str, output_file: str = None) -> None:
    """
    Process a JSON file and fix all encoding issues.
    
    Args:
        input_file: Path to input JSON file
        output_file: Path to output file (if None, overwrites input)
    """
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        fixed_data = fix_data_structure(data)
        
        output_path = output_file or input_file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(fixed_data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ Fixed encoding issues in {input_file}")
        if output_file:
            print(f"  Saved to {output_file}")
        else:
            print(f"  File updated in place")
            
    except FileNotFoundError:
        print(f"✗ Error: File '{input_file}' not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"✗ Error: Invalid JSON in '{input_file}': {e}")
        sys.exit(1)


def demo():
    """Demonstrate the fixing functionality with examples."""
    test_cases = [
        "D\u00c3\u00b3ra",  # Double-encoded "Dóra"
        "D\u00c3\u0192\u00c2\u00b3ra",  # Triple-encoded "Dóra"
        "DÃƒÂ³ra",  # Triple-encoded "Dóra" (alternate form)
        "MÃƒÂ©szÃƒÂ¡ros",  # Triple-encoded "Mészáros"
        "Jos\u00c3\u00a9",  # Double-encoded "José"
        "M\u00c3\u00bcller",  # Double-encoded "Müller"
        "Fran\u00c3\u00a7ois",  # Double-encoded "François"
        "Normal text",  # Should remain unchanged
    ]
    
    print("Demo: Fixing double-encoded strings\n")
    print(f"{'Original':<30} {'Fixed':<20}")
    print("-" * 50)
    
    for text in test_cases:
        fixed = fix_double_encoding(text)
        print(f"{text:<30} {fixed:<20}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None
        process_json_file(input_file, output_file)
    else:
        print("UTF-8 Double Encoding Fixer\n")
        print("Usage:")
        print("  python script.py input.json [output.json]")
        print("  (If output.json is omitted, input.json will be updated in place)\n")
        print("Or run without arguments to see a demo:\n")
        demo()
        print("\nExample for direct use in code:")
        print("  from script import fix_double_encoding, fix_data_structure")
        print('  fixed = fix_double_encoding("D\\u00c3\\u00b3ra")')
        print('  # Returns: "Dóra"')