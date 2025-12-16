#!/usr/bin/env python3
"""
Script to fix double-encoded UTF-8 strings in text data.
Handles common encoding issues from web scraping.

Supported Modes:
1. JSON Cleanup: Recursively traverses JSON structure and fixes encoding issues in all string values.
2. CSV Extraction: Reads a CSV, fixes encoding in 'Name' and 'Aliases', and extracts/defaults
   'Nationality' and 'Ethnicity' columns to a standard format.

Usage:
    python encoding_fixer.py <input_file> [output_file]
"""

import json
import csv
import sys
from typing import Any


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
            print("  File updated in place")
            
    except FileNotFoundError:
        print(f"✗ Error: File '{input_file}' not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"✗ Error: Invalid JSON in '{input_file}': {e}")
        sys.exit(1)

def process_csv_file(input_file: str, output_file: str = None) -> None:
    """
    Process CSV: Fix names/aliases and extract specific demographics.
    Defaults missing columns to 'Unknown'.
    """
    # Columns we want to output
    TARGET_COLS = ['Name', 'Aliases', 'Nationality', 'Ethnicity']
    # Columns that need encoding fixes
    FIX_COLS = ['Name', 'Aliases']

    output_path = output_file or input_file

    try:
        with open(input_file, 'r', encoding='utf-8', newline='') as f_in:
            reader = csv.DictReader(f_in)
           
            rows_out = []
            for row in reader:
                new_row = {}
                for col in TARGET_COLS:
                    # Get value, default to 'Unknown' if missing or empty
                    val = row.get(col)
                    if not val or val.strip() == '':
                        val = 'Unknown'
                    
                    # Fix encoding if it's a name field
                    if col in FIX_COLS:
                        val = fix_double_encoding(val)
                    
                    new_row[col] = val
                rows_out.append(new_row)

        with open(output_path, 'w', encoding='utf-8', newline='') as f_out:
            writer = csv.DictWriter(f_out, fieldnames=TARGET_COLS)
            writer.writeheader()
            writer.writerows(rows_out)

        print(f"✓ Processed CSV {input_file}")
        print(f"  - Fixed encoding in: {', '.join(FIX_COLS)}")
        print(f"  - Extracted columns: {', '.join(TARGET_COLS)}")
        if output_file:
            print(f"  Saved to {output_file}")
            
    except FileNotFoundError:
        print(f"✗ Error: File '{input_file}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error processing CSV '{input_file}': {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python encoding_fixer.py <input_file> [output_file]")
        print("Supported formats: .json, .csv")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    if input_file.lower().endswith('.csv'):
        process_csv_file(input_file, output_file)
    else:
        process_json_file(input_file, output_file)