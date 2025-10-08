import csv
import json
from collections import defaultdict
import os

# --- Configuration ---
CSV_FILENAME = 'performers.csv' 
TALENT_GEN_DATA_FILENAME = 'talent_generation_data.json' # To preserve male names
OUTPUT_JSON_FILENAME = 'aliases_structured.json'

# CSV Column Names (must match your file)
NAME_COLUMN = 'Name'
ALIASES_COLUMN = 'Aliases'
ETHNICITY_COLUMN = 'Ethnicity'

# Mapping from CSV ethnicity values to your game's ethnicity values.
# Add any other mappings you need here.
ETHNICITY_MAP = {
    'Caucasian': 'White',
    'Mixed': 'White'  # Mapping 'Mixed' to a common fallback
}

# Your game must recognize these ethnicities. Names with unmapped ethnicities will be skipped.
VALID_GAME_ETHNICITIES = [
    "White", "Black", "Latin", "Asian", "Japanese", "Korean", "Russian", "Thai"
]
# --- End Configuration ---

def process_aliases():
    """
    Reads the original talent generation data and the new alias CSV,
    then merges them into a single structured JSON file.
    """
    # Using defaultdict for easier nested dictionary creation
    # Final structure: {ethnicity: {gender: {part: [name1, name2, ...]}}}
    aliases = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    # 1. Pre-load existing male/unisex names from the original JSON file
    #    This ensures male talent generation still works.
    try:
        with open(TALENT_GEN_DATA_FILENAME, 'r', encoding='utf-8') as f:
            gen_data = json.load(f).get('aliases', {})
            male_first = gen_data.get('male_first', [])
            unisex_last = gen_data.get('unisex_last', [])
            
            # We'll assign these to a default ethnicity, as the original file had no mapping.
            # Most common male names in the original list are of Western origin.
            default_ethnicity_for_males = "White"
            if male_first:
                aliases[default_ethnicity_for_males]['Male']['first'].extend(male_first)
                aliases[default_ethnicity_for_males]['Male']['single'].extend(male_first) # Can be single names too
            if unisex_last:
                aliases[default_ethnicity_for_males]['Male']['last'].extend(unisex_last)
                aliases[default_ethnicity_for_males]['Female']['last'].extend(unisex_last)

        print(f"Pre-loaded {len(male_first)} male first names and {len(unisex_last)} last names.")

    except FileNotFoundError:
        print(f"Warning: '{TALENT_GEN_DATA_FILENAME}' not found. Male names will be very limited.")
    except json.JSONDecodeError:
        print(f"Warning: Could not parse '{TALENT_GEN_DATA_FILENAME}'. Male names will be very limited.")


    # 2. Process the new, richer female alias data from the CSV
    if not os.path.exists(CSV_FILENAME):
        print(f"ERROR: '{CSV_FILENAME}' not found. Cannot add female aliases.")
        # Proceed to write out the file with just the pre-loaded male names if any
    else:
        print(f"Processing female aliases from '{CSV_FILENAME}'...")
        try:
            with open(CSV_FILENAME, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Map ethnicity from CSV value to game value
                    raw_ethnicity = row.get(ETHNICITY_COLUMN, '').strip()
                    game_ethnicity = ETHNICITY_MAP.get(raw_ethnicity, raw_ethnicity)

                    if not game_ethnicity or game_ethnicity not in VALID_GAME_ETHNICITIES:
                        # print(f"Skipping row with unmapped ethnicity: '{raw_ethnicity}'")
                        continue

                    # Collect all possible names for this person
                    all_names_for_row = set()
                    
                    # Add the 'Name' column value
                    main_name = row.get(NAME_COLUMN, '').strip()
                    if main_name:
                        all_names_for_row.add(main_name)

                    # Add the 'Aliases' column values, splitting by comma
                    alias_str = row.get(ALIASES_COLUMN, '').strip()
                    if alias_str and alias_str.lower() != 'unknown':
                        # Split by comma and strip whitespace from each part
                        individual_aliases = [name.strip() for name in alias_str.split(',')]
                        all_names_for_row.update(individual_aliases)
                    
                    # Process each collected name
                    for alias in all_names_for_row:
                        parts = alias.split()
                        if len(parts) == 1:
                            aliases[game_ethnicity]['Female']['single'].append(parts[0])
                            aliases[game_ethnicity]['Female']['first'].append(parts[0])
                        elif len(parts) > 1:
                            aliases[game_ethnicity]['Female']['first'].append(parts[0])
                            aliases[game_ethnicity]['Female']['last'].append(parts[-1])
        
        except FileNotFoundError:
            print(f"Error: {CSV_FILENAME} not found.")
        except KeyError as e:
            print(f"ERROR: CSV is missing an expected column: {e}. Check your column names in the script config.")
            return

    # 3. Clean up: remove duplicates and sort lists for consistency
    print("Removing duplicates and sorting...")
    for ethnicity, genders in aliases.items():
        for gender, parts in genders.items():
            for part, names in parts.items():
                aliases[ethnicity][gender][part] = sorted(list(set(names)))
    
    # 4. Write the final merged and structured data to the output JSON
    print(f"Writing structured data to '{OUTPUT_JSON_FILENAME}'...")
    with open(OUTPUT_JSON_FILENAME, 'w', encoding='utf-8') as f:
        json.dump(aliases, f, indent=2)
        
    print("Processing complete.")

if __name__ == '__main__':
    process_aliases()