import json
import os

NAMES_JSON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "talent_generation", "names_by_culture.json")

def clean_data(data):
    """Recursively traverses the JSON, de-duping and sorting lists."""
    if isinstance(data, dict):
        return {k: clean_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        # Convert to set to remove duplicates, then sort alphabetically
        unique_sorted = sorted(list(set([str(x).strip() for x in data if x])))
        return unique_sorted
    else:
        return data

def format_compact_list(data, indent_level):
    """Formats a list of strings with 10 items per line."""
    if not data:
        return "[]"
    
    json_items = [json.dumps(x, ensure_ascii=False) for x in data]
    indent = "  " * indent_level
    inner_indent = "  " * (indent_level + 1)
    lines = ["["]
    
    chunk_size = 10
    for i in range(0, len(json_items), chunk_size):
        chunk = json_items[i:i+chunk_size]
        # Join with comma space
        line_str = ", ".join(chunk)
        # Add trailing comma if not the last line
        if i + chunk_size < len(json_items):
            line_str += ","
        lines.append(f"{inner_indent}{line_str}")
    
    lines.append(f"{indent}]")
    return "\n".join(lines)

def custom_dump(data, indent_level=0):
    """Recursive dumper that compacts lists of strings and sorts keys."""
    indent = "  " * indent_level
    
    if isinstance(data, dict):
        if not data:
            return "{}"
        lines = ["{"]
        # Sort keys for deterministic output
        keys = sorted(data.keys())
        for idx, key in enumerate(keys):
            val = data[key]
            formatted_val = custom_dump(val, indent_level + 1)
            comma = "," if idx < len(keys) - 1 else ""
            lines.append(f'{indent}  "{key}": {formatted_val}{comma}')
        lines.append(f"{indent}}}")
        return "\n".join(lines)
        
    elif isinstance(data, list) and all(isinstance(x, str) for x in data):
        return format_compact_list(data, indent_level)
    
    else:
        # Fallback for other types
        return json.dumps(data, ensure_ascii=False)

def main():
    if not os.path.exists(NAMES_JSON_PATH):
        print(f"Error: Could not find file at {NAMES_JSON_PATH}")
        return

    print(f"Processing {NAMES_JSON_PATH}...")
    
    try:
        with open(NAMES_JSON_PATH, "r", encoding="utf-8") as f:
            content = json.load(f)
            
        cleaned_content = clean_data(content)
        formatted_json = custom_dump(cleaned_content)
        
        with open(NAMES_JSON_PATH, "w", encoding="utf-8") as f:
            f.write(formatted_json)
            
        print("Success! Lists have been de-duped, sorted, and formatted (10 per row).")
        
    except json.JSONDecodeError:
        print("Error: The JSON file is malformed.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()