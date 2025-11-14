import sqlite3
import json
import os

# Database will be created in the project root (parent of scripts/)
DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "game_data.sqlite")

def create_tables(cursor):
    """Creates all the necessary tables in the database."""
    print("Creating tables...")

    # game_config
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS game_config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)

    # talent_generation_data and talent_affinity_data
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS generation_weights (
        category TEXT NOT NULL,
        name TEXT NOT NULL,
        weight INTEGER NOT NULL,
        PRIMARY KEY (category, name)
    )
    """)

    # New tables for nationality-based generation
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS nationalities (
        name TEXT PRIMARY KEY,
        weight REAL NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS nationality_locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nationality_name TEXT NOT NULL,
        location_name TEXT NOT NULL,
        weight INTEGER NOT NULL,
        FOREIGN KEY (nationality_name) REFERENCES nationalities (name)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS nationality_ethnicities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nationality_name TEXT NOT NULL,
        ethnicity_name TEXT NOT NULL, -- This is the sub-group, e.g., 'Western European'
        weight INTEGER NOT NULL,
        FOREIGN KEY (nationality_name) REFERENCES nationalities (name)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cultural_names (
        culture_key TEXT NOT NULL,
        gender TEXT NOT NULL,
        part TEXT NOT NULL, -- 'first', 'last', or 'single'
        name TEXT NOT NULL,
        PRIMARY KEY (culture_key, gender, part, name)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS regions (
        name TEXT PRIMARY KEY
    )
    """)
   
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS region_locations (
        region_name TEXT NOT NULL,
        location_name TEXT NOT NULL,
        PRIMARY KEY (region_name, location_name),
        FOREIGN KEY (region_name) REFERENCES regions (name)
    )
    """)

    # NEW: Table for travel costs between regions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS region_travel_costs (
        origin_region TEXT NOT NULL,
        destination_region TEXT NOT NULL,
        cost INTEGER NOT NULL,
        fatigue INTEGER NOT NULL,
        PRIMARY KEY (origin_region, destination_region),
        FOREIGN KEY (origin_region) REFERENCES regions (name),
        FOREIGN KEY (destination_region) REFERENCES regions (name)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ethnicity_definitions (
        name TEXT PRIMARY KEY, -- Sub-group, e.g., 'Western European'
        primary_ethnicity TEXT NOT NULL -- Main group, e.g., 'White'
    )
    """)
    
    # talent_affinities
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS talent_affinities (
        category TEXT NOT NULL, -- e.g., 'Female', 'Male', 'BoobSize', 'DickSize'
        name TEXT NOT NULL,     -- e.g., 'Teen', 'MILF', 'C', 'default'
        data_json TEXT NOT NULL,
        PRIMARY KEY (category, name)
    )
    """)

    # market
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS viewer_groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        inherits_from TEXT,
        market_share_percent REAL NOT NULL,
        spending_power REAL NOT NULL,
        focus_bonus REAL NOT NULL,
        popularity_spillover_json TEXT,
        preferences_json TEXT
    )
    """)

    # scene_tags
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scene_tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        orientation TEXT,
        type TEXT NOT NULL,
        concept TEXT,
        is_template INTEGER DEFAULT 0,
        categories_json TEXT,
        slots_json TEXT,
        expands_to_json TEXT,
        is_auto_taggable INTEGER DEFAULT 0,
        validation_rule_json TEXT,
        auto_detection_rule_json TEXT,
        quality_source_json TEXT,
        revenue_weights_json TEXT,
        scene_wide_modifiers_json TEXT, 
        ethnicity TEXT,
        gender TEXT,
        tooltip TEXT,
        appeal_weight REAL NOT NULL DEFAULT 10.0,
        UNIQUE(name, orientation, type)
    )
    """)
    
    # production_settings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS production_settings_definitions (
        category TEXT NOT NULL,
        tier_name TEXT NOT NULL,
        cost_per_scene INTEGER,
        cost_multiplier REAL,
        quality_modifier REAL NOT NULL,
        description TEXT,
        bad_event_chance_modifier REAL NOT NULL DEFAULT 1.0,
        good_event_chance_modifier REAL NOT NULL DEFAULT 1.0,
        PRIMARY KEY (category, tier_name)
    )
    """)

    # post_production_settings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS post_production_definitions (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        cost INTEGER NOT NULL,
        weeks INTEGER NOT NULL,
        description TEXT,
        base_quality_modifier REAL NOT NULL,
        synergy_mods_json TEXT
    )
    """)

    # on_set_policies
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS on_set_policies_definitions (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        cost_per_bloc INTEGER NOT NULL DEFAULT 0
    )
    """)

    # scene_events
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scene_events (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        category TEXT NOT NULL,
        type TEXT NOT NULL,
        base_chance REAL NOT NULL,
        choices_json TEXT,
        triggering_tiers_json TEXT,
        triggering_conditions_json TEXT
    )
    """)
    
    # talent_archetypes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS talent_archetypes (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        weight INTEGER NOT NULL,
        action_preferences_json TEXT,
        thematic_preferences_json TEXT,
        hard_limits_json TEXT,
        stat_modifiers_json TEXT,
        max_scene_partners INTEGER NOT NULL DEFAULT 10,
        concurrency_limits_json TEXT
    )
    """)
    
    print("Tables created successfully.")


def migrate_config(cursor, data):
    print("Migrating game_config.json...")
    for key, value in data.items():
        # If the value is a dictionary or list, store it as a JSON string
        if isinstance(value, (dict, list)):
            value_to_store = json.dumps(value)
        else:
            value_to_store = str(value)
        cursor.execute("INSERT OR REPLACE INTO game_config (key, value) VALUES (?, ?)", (key, value_to_store))
    print(f"{cursor.rowcount} config entries migrated.")

def migrate_talent_generation(cursor, data):
    print("Migrating talent_generation_data.json...")
    weights_count = 0
    for category_name in ["genders", "physiques", "cup_sizes"]:
        if category_name in data:
            for item in data[category_name]:
                cursor.execute("INSERT OR REPLACE INTO generation_weights (category, name, weight) VALUES (?, ?, ?)",
                               (category_name, item['name'], item['weight']))
                weights_count += 1
    
    eth_count = 0
    for primary_group in data.get("ethnicities", []):
        primary_name = primary_group['name']
        if not primary_group.get('sub_groups'): # Handle ethnicities with no sub-groups
             cursor.execute("INSERT OR REPLACE INTO ethnicity_definitions (name, primary_ethnicity) VALUES (?, ?)",
                               (primary_name, primary_name))
             eth_count += 1
        else:
            for sub_group_name in primary_group['sub_groups']:
                cursor.execute("INSERT OR REPLACE INTO ethnicity_definitions (name, primary_ethnicity) VALUES (?, ?)",
                            (sub_group_name, primary_name))
                eth_count += 1
    
    print(f"{weights_count} talent generation weight entries migrated.")
    print(f"{eth_count} ethnicity definitions migrated.")

def migrate_nationality_data(cursor, data):
    """Migrates nationality weights, locations, and ethnicities."""
    print("Migrating nationality_weights.json...")
    nat_count, loc_count, eth_count = 0, 0, 0
    for nationality in data['nationalities']:
        cursor.execute("INSERT OR REPLACE INTO nationalities (name, weight) VALUES (?, ?)", (nationality['name'], nationality['weight']))
        nat_count += 1

    for nat_name, locations in data['locations_by_nationality'].items():
        for loc in locations:
            cursor.execute("INSERT OR REPLACE INTO nationality_locations (nationality_name, location_name, weight) VALUES (?, ?, ?)", (nat_name, loc['name'], loc['weight']))
            loc_count += 1
            
    for nat_name, ethnicities in data['ethnicities_by_nationality'].items():
        for eth in ethnicities:
            cursor.execute("INSERT OR REPLACE INTO nationality_ethnicities (nationality_name, ethnicity_name, weight) VALUES (?, ?, ?)", (nat_name, eth['name'], eth['weight']))
            eth_count += 1
            
    print(f"{nat_count} nationalities, {loc_count} nationality locations, and {eth_count} nationality ethnicities migrated.")

def migrate_regions(cursor, data):
    print("Migrating regions.json...")
    reg_count, loc_count = 0, 0
    for region in data['regions']:
        cursor.execute("INSERT OR REPLACE INTO regions (name) VALUES (?)", (region['name'],))
        reg_count += 1
        for location in region['locations']:
            cursor.execute("INSERT OR REPLACE INTO region_locations (region_name, location_name) VALUES (?, ?)", (region['name'], location))
            loc_count += 1
    print(f"{reg_count} regions and {loc_count} region locations migrated.")

# NEW: Migration function for travel costs
def migrate_travel_costs(cursor, data):
    """Migrates the travel cost matrix from regions.json."""
    print("Migrating travel matrix...")
    count = 0
    for entry in data.get('travel_matrix', []):
        origin = entry.get('from')
        destination = entry.get('to')
        cost = entry.get('cost')
        fatigue = entry.get('fatigue')
        if all([origin, destination, cost is not None, fatigue is not None]):
            # Insert both directions for easier lookup
            cursor.execute("""
                INSERT OR REPLACE INTO region_travel_costs (origin_region, destination_region, cost, fatigue)
                VALUES (?, ?, ?, ?)
            """, (origin, destination, cost, fatigue))
            cursor.execute("""
                INSERT OR REPLACE INTO region_travel_costs (origin_region, destination_region, cost, fatigue)
                VALUES (?, ?, ?, ?)
            """, (destination, origin, cost, fatigue))
            count += 1
    print(f"{count*2} travel cost entries migrated (symmetric).")


def migrate_names(cursor, data):
    print("Migrating names_by_culture.json...")
    count = 0
    names_data = data['names_by_culture']

    for culture_key, parts_data in names_data.items():
        for part_key, names in parts_data.items():
            # Handle shared names like 'last' and 'single' by adding them for both genders
            if part_key in ("last", "single"):
                genders = ["Male", "Female"]
                part = part_key
                for gender in genders:
                    for name in names:
                        cursor.execute("INSERT OR REPLACE INTO cultural_names (culture_key, gender, part, name) VALUES (?, ?, ?, ?)",
                                       (culture_key, gender, part, name))
                        count += 1
            # Handle specific names like 'male_first'
            elif "_" in part_key:
                try:
                    gender_str, part = part_key.split("_", 1)
                    gender = gender_str.capitalize()  # 'male' -> 'Male'
                    for name in names:
                        cursor.execute("INSERT OR REPLACE INTO cultural_names (culture_key, gender, part, name) VALUES (?, ?, ?, ?)",
                                       (culture_key, gender, part, name))
                        count += 1
                except ValueError:
                    print(f"Warning: Could not parse part_key '{part_key}' in names_by_culture.json. Skipping.")
    print(f"{count} cultural name entries migrated.")

def migrate_talent_affinities(cursor, data):
    """Migrates all talent affinities into the unified talent_affinities table."""
    print("Migrating talent_affinity_data.json...")
    count = 0

    for category, items in data.items():
        if category in ["Male", "Female"]:  # Age affinities
            for affinity_name, details in items.items():
                cursor.execute("""
                    INSERT OR REPLACE INTO talent_affinities (category, name, data_json)
                    VALUES (?, ?, ?)
                """, (category, affinity_name, json.dumps(details)))
                count += 1
        elif category == "BoobSize":  # Boob size affinities
            for cup_size, affinities in items.items():
                cursor.execute("""
                    INSERT OR REPLACE INTO talent_affinities (category, name, data_json)
                    VALUES (?, ?, ?)
                """, (category, cup_size, json.dumps(affinities)))
                count += 1
        elif category == "DickSize":  # Dick size affinity
            # The entire DickSize object is stored under a single 'default' name
            cursor.execute("""
                INSERT OR REPLACE INTO talent_affinities (category, name, data_json)
                VALUES (?, ?, ?)
            """, (category, 'default', json.dumps(items)))
            count += 1
            
    print(f"{count} talent affinity entries migrated into the unified table.")


def migrate_market(cursor, data):
    print("Migrating market.json...")
    count = 0
    for group in data.get("viewer_groups", []):
        cursor.execute("""
            INSERT OR REPLACE INTO viewer_groups (name, inherits_from, market_share_percent, spending_power, focus_bonus, popularity_spillover_json, preferences_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            group['name'],
            group.get('inherits_from'),
            group['market_share_percent'],
            group['spending_power'],
            group['focus_bonus'],
            json.dumps(group.get('popularity_spillover', {})),
            json.dumps(group.get('preferences', {}))
        ))
        count += 1
    print(f"{count} viewer groups migrated.")


def migrate_scene_tags(cursor, all_tags_data):
    """Migrates thematic, physical, and action tags into the unified scene_tags table."""
    print("Migrating all scene tags...")
    count = 0
    for tag in all_tags_data:
        is_template = 1 if tag.get('is_template', False) else 0
        is_auto_taggable = 1 if tag.get('is_auto_taggable', False) else 0
        appeal_weight = tag.get('appeal_weight') or 10.0

        cursor.execute("""
            INSERT OR REPLACE INTO scene_tags (
                name, orientation, type, concept, is_template, is_auto_taggable, 
                categories_json, slots_json, expands_to_json, validation_rule_json,
                auto_detection_rule_json,
                quality_source_json, revenue_weights_json, scene_wide_modifiers_json, 
                ethnicity, gender, tooltip, appeal_weight
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tag.get('name'), tag.get('orientation'), tag.get('type'), tag.get('concept'),
            is_template, is_auto_taggable, json.dumps(tag.get('categories')), 
            json.dumps(tag.get('slots')), json.dumps(tag.get('expands_to')), 
            json.dumps(tag.get('validation_rule')), 
            json.dumps(tag.get('auto_detection_rule')),
            json.dumps(tag.get('quality_source')), 
            json.dumps(tag.get('revenue_weights')), json.dumps(tag.get('scene_wide_modifiers')),
            tag.get('ethnicity'), tag.get('gender'), tag.get('tooltip'), appeal_weight
        ))
        count += 1
    print(f"{count} total scene tags migrated.")

def migrate_production_settings(cursor, data):
    """Migrates production settings from JSON to the database."""
    print("Migrating production_settings.json...")
    count = 0
    for category, tiers in data.items():
        for tier in tiers:
            cursor.execute("""
                INSERT OR REPLACE INTO production_settings_definitions (
                    category, tier_name, cost_per_scene, cost_multiplier, quality_modifier, description,
                    bad_event_chance_modifier, good_event_chance_modifier
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                category,
                tier.get('tier_name'),
                tier.get('cost_per_scene'),
                tier.get('cost_multiplier'),
                tier.get('quality_modifier'),
                tier.get('description'),
                tier.get('bad_event_chance_modifier', 1.0),
                tier.get('good_event_chance_modifier', 1.0)
            ))
            count += 1
    print(f"{count} production setting entries migrated.")

def migrate_post_production_settings(cursor, data):
    """Migrates post-production settings from JSON to the database."""
    print("Migrating post_production_settings.json...")
    count = 0
    for tier in data.get("editing_tiers", []):
        cursor.execute("""
            INSERT OR REPLACE INTO post_production_definitions (
                id, name, cost, weeks, description, base_quality_modifier, synergy_mods_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            tier.get('id'),
            tier.get('name'),
            tier.get('cost'),
            tier.get('weeks'),
            tier.get('description'),
            tier.get('base_quality_modifier'),
            json.dumps(tier.get('synergy_mods'))
        ))
        count += 1
    print(f"{count} post-production setting entries migrated.")

def migrate_on_set_policies(cursor, data):
    """Migrates on-set policies from JSON to the database."""
    print("Migrating on_set_policies.json...")
    count = 0
    for policy in data:
        cursor.execute("""
            INSERT OR REPLACE INTO on_set_policies_definitions (
                id, name, description, cost_per_bloc
            ) VALUES (?, ?, ?, ?)
        """, (
            policy.get('id'),
            policy.get('name'),
            policy.get('description'),
            policy.get('cost_per_bloc', 0)
        ))
        count += 1
    print(f"{count} on-set policy entries migrated.")


def migrate_scene_events(cursor, data):
    """Migrates scene events from JSON to the database."""
    print("Migrating scene_events.json...")
    count = 0
    for event in data:
        cursor.execute("""
            INSERT OR REPLACE INTO scene_events (
                id, name, description, category, type, base_chance, 
                choices_json, triggering_tiers_json, triggering_conditions_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.get('id'),
            event.get('name'),
            event.get('description'),
            event.get('category'),
            event.get('type'),
            event.get('base_chance'),
            json.dumps(event.get('choices')),
            json.dumps(event.get('triggering_tiers')),
            json.dumps(event.get('triggering_conditions'))
        ))
        count += 1
    print(f"{count} scene events migrated.")

def migrate_talent_archetypes(cursor, data):
    """Migrates talent archetypes from JSON to the database."""
    print("Migrating talent_archetypes.json...")
    count = 0
    for archetype in data:
        cursor.execute("""
        INSERT OR REPLACE INTO talent_archetypes (
        id, name, description, weight, action_preferences_json,
        thematic_preferences_json, hard_limits_json, stat_modifiers_json,
        max_scene_partners, concurrency_limits_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
        archetype.get('id'),
        archetype.get('name'),
        archetype.get('description'),
        archetype.get('weight'),
        json.dumps(archetype.get('action_preferences', {})),
        json.dumps(archetype.get('thematic_preferences', {})),
        json.dumps(archetype.get('hard_limits', [])),
        json.dumps(archetype.get('stat_modifiers', {})),
        archetype.get('max_scene_partners', 10),
        json.dumps(archetype.get('concurrency_limits', {}))
        ))
        count += 1
    print(f"{count} talent archetype entries migrated.")

def main():
    # Get the project root directory (parent of scripts/)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    db_path = os.path.join(project_root, "game_data.sqlite")

    if os.path.exists(db_path):
        print(f"'{db_path}' already exists. Deleting to start fresh.")
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    create_tables(cursor)

    # Helper function to load JSON files from the new structure
    def load_json(relative_path):
        path = os.path.join(project_root, relative_path)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # Load JSON files and run migrations with updated paths
    try:
        migrate_config(cursor, load_json("game_config.json"))
        migrate_talent_generation(cursor, load_json("talent_generation/talent_generation_data.json"))
        migrate_nationality_data(cursor, load_json("talent_generation/nationality_weights.json"))
        
        # Load regions.json once and pass it to both migration functions
        regions_data = load_json("regions.json")
        migrate_regions(cursor, regions_data)
        migrate_travel_costs(cursor, regions_data)

        migrate_names(cursor, load_json("talent_generation/names_by_culture.json"))

        migrate_talent_affinities(cursor, load_json("talent_generation/talent_affinity_data.json"))
        migrate_market(cursor, load_json("market.json"))
        all_tags = (
            load_json("tags/action_tags.json") +
            load_json("tags/physical_tags.json") +
            load_json("tags/thematic_tags.json")
        )
        migrate_scene_tags(cursor, all_tags)
        migrate_production_settings(cursor, load_json("scene_settings/production_settings.json"))
        migrate_post_production_settings(cursor, load_json("scene_settings/post_production_settings.json"))
        migrate_on_set_policies(cursor, load_json("scene_settings/on_set_policies.json"))
        migrate_scene_events(cursor, load_json("events/scene_events.json"))
        migrate_talent_archetypes(cursor, load_json("talent_generation/talent_archetypes.json"))

    except FileNotFoundError as e:
        print(f"ERROR: Missing data file '{e.filename}'. Cannot continue migration.")
        conn.rollback()
    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    else:
        print(f"\nMigration completed successfully! Database created at '{db_path}'.")
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()