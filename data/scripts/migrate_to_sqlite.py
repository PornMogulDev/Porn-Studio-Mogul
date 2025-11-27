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

    # Tables for nationality-based generation
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

    # Table for travel costs between regions
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
    
    # production_departments (Replaces old production_settings)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS production_departments (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        base_weight REAL NOT NULL,
        min_budget INTEGER NOT NULL,
        soft_cap_budget INTEGER NOT NULL,
        curve_type TEXT NOT NULL,
        impacts_json TEXT
    )
    """)

    # visual_styles
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS visual_styles (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        budget_efficiency_modifier REAL NOT NULL,
        department_multipliers_json TEXT
    )
    """)

    # production_jobs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS production_jobs (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        is_mandatory INTEGER NOT NULL,
        base_stress_load REAL NOT NULL,
        base_fatigue_load REAL NOT NULL,
        primary_skill TEXT
    )
    """)

    # production_locations
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS production_locations (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        recommended_budget INTEGER NOT NULL,
        min_budget INTEGER NOT NULL,
        curve_type TEXT NOT NULL,
        tags_json TEXT,
        simulation_modifiers_json TEXT,
        synergy_bonuses_json TEXT,
        synergy_penalties_json TEXT
    )
    """)

    # picture_set_types
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS picture_set_types (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        budget_efficiency REAL NOT NULL,
        min_budget INTEGER NOT NULL,
        soft_cap_budget INTEGER NOT NULL,
        momentum_impact REAL NOT NULL,
        stress_impact REAL NOT NULL,
        requires_photographer INTEGER NOT NULL
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
        stat_modifiers_json TEXT,
        max_scene_partners_json TEXT, 
        concurrency_limits_json TEXT,
        dynamic_preference_weights_json TEXT,
        trait_weights_json TEXT
    )
    """)

    # traits
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS traits (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        type TEXT NOT NULL,
        modifiers_json TEXT,
        conflicts_with_json TEXT,
        policy_requirements_json TEXT,
        action_preference_modifiers_json TEXT,
        thematic_preference_modifiers_json TEXT,
        concurrency_modifiers_json TEXT
    )
    """)

    # accommodation_tiers
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accommodation_tiers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        cost_per_week INTEGER NOT NULL,
        pickiness_requirement INTEGER NOT NULL,
        description TEXT
    )
    """)
    
    print("Tables created successfully.")


def migrate_config(cursor, data):
    print("Migrating game_config.json...")
    for key, value in data.items():
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
        if not primary_group.get('sub_groups'): 
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

def migrate_travel_costs(cursor, data):
    print("Migrating travel matrix...")
    count = 0
    for entry in data.get('travel_matrix', []):
        origin = entry.get('from')
        destination = entry.get('to')
        cost = entry.get('cost')
        fatigue = entry.get('fatigue')
        if all([origin, destination, cost is not None, fatigue is not None]):
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
            if part_key in ("last", "single"):
                genders = ["Male", "Female"]
                part = part_key
                for gender in genders:
                    for name in names:
                        cursor.execute("INSERT OR REPLACE INTO cultural_names (culture_key, gender, part, name) VALUES (?, ?, ?, ?)",
                                       (culture_key, gender, part, name))
                        count += 1
            elif "_" in part_key:
                try:
                    gender_str, part = part_key.split("_", 1)
                    gender = gender_str.capitalize()
                    for name in names:
                        cursor.execute("INSERT OR REPLACE INTO cultural_names (culture_key, gender, part, name) VALUES (?, ?, ?, ?)",
                                       (culture_key, gender, part, name))
                        count += 1
                except ValueError:
                    print(f"Warning: Could not parse part_key '{part_key}' in names_by_culture.json. Skipping.")
    print(f"{count} cultural name entries migrated.")

def migrate_talent_affinities(cursor, data):
    print("Migrating talent_affinity_data.json...")
    count = 0
    for category, items in data.items():
        if category in ["Male", "Female"]:
            for affinity_name, details in items.items():
                cursor.execute("""
                    INSERT OR REPLACE INTO talent_affinities (category, name, data_json)
                    VALUES (?, ?, ?)
                """, (category, affinity_name, json.dumps(details)))
                count += 1
        elif category == "BoobSize":
            for cup_size, affinities in items.items():
                cursor.execute("""
                    INSERT OR REPLACE INTO talent_affinities (category, name, data_json)
                    VALUES (?, ?, ?)
                """, (category, cup_size, json.dumps(affinities)))
                count += 1
        elif category == "DickSize":
            cursor.execute("""
                INSERT OR REPLACE INTO talent_affinities (category, name, data_json)
                VALUES (?, ?, ?)
            """, (category, 'default', json.dumps(items)))
            count += 1
    print(f"{count} talent affinity entries migrated.")

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

def migrate_production_departments(cursor, data):
    print("Migrating production_departments.json...")
    count = 0
    for dept in data:
        cursor.execute("""
            INSERT OR REPLACE INTO production_departments (
                id, name, description, base_weight, min_budget, 
                soft_cap_budget, curve_type, impacts_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dept.get('id'),
            dept.get('name'),
            dept.get('description'),
            dept.get('base_weight'),
            dept.get('min_budget'),
            dept.get('soft_cap_budget'),
            dept.get('curve_type'),
            json.dumps(dept.get('impacts', []))
        ))
        count += 1
    print(f"{count} production departments migrated.")

def migrate_visual_styles(cursor, data):
    print("Migrating visual_styles.json...")
    count = 0
    for style in data:
        cursor.execute("""
            INSERT OR REPLACE INTO visual_styles (
                id, name, description, budget_efficiency_modifier, department_multipliers_json
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            style.get('id'),
            style.get('name'),
            style.get('description'),
            style.get('budget_efficiency_modifier'),
            json.dumps(style.get('department_multipliers', {}))
        ))
        count += 1
    print(f"{count} visual styles migrated.")

def migrate_production_jobs(cursor, data):
    print("Migrating production_jobs.json...")
    count = 0
    for job in data:
        cursor.execute("""
            INSERT OR REPLACE INTO production_jobs (
                id, name, description, is_mandatory, base_stress_load, 
                base_fatigue_load, primary_skill
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            job.get('id'),
            job.get('name'),
            job.get('description'),
            1 if job.get('is_mandatory') else 0,
            job.get('base_stress_load'),
            job.get('base_fatigue_load'),
            job.get('primary_skill')
        ))
        count += 1
    print(f"{count} production jobs migrated.")

def migrate_production_locations(cursor, data):
    print("Migrating production_locations.json...")
    count = 0
    for loc in data:
        cursor.execute("""
            INSERT OR REPLACE INTO production_locations (
                id, name, recommended_budget, min_budget, curve_type,
                tags_json, simulation_modifiers_json,  
                synergy_bonuses_json, synergy_penalties_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            loc.get('id'),
            loc.get('name'),
            loc.get('recommended_budget'),
            loc.get('min_budget'),
            loc.get('curve_type', 'linear'),
            json.dumps(loc.get('tags', [])),
            json.dumps(loc.get('simulation_modifiers', {})),
            json.dumps(loc.get('synergy_bonuses', [])),
            json.dumps(loc.get('synergy_penalties', []))
        ))
        count += 1
    print(f"{count} production locations migrated.")

def migrate_picture_set_types(cursor, data):
    print("Migrating picture_set_types.json...")
    count = 0
    for ps_type in data:
        cursor.execute("""
            INSERT OR REPLACE INTO picture_set_types (
                id, name, description, budget_efficiency, min_budget, 
                soft_cap_budget, momentum_impact, stress_impact, requires_photographer
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ps_type.get('id'),
            ps_type.get('name'),
            ps_type.get('description'),
            ps_type.get('budget_efficiency'),
            ps_type.get('min_budget'),
            ps_type.get('soft_cap_budget'),
            ps_type.get('momentum_impact'),
            ps_type.get('stress_impact'),
            1 if ps_type.get('requires_photographer') else 0
        ))
        count += 1
    print(f"{count} picture set types migrated.")

def migrate_post_production_settings(cursor, data):
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
    print("Migrating talent_archetypes.json...")
    count = 0
    for archetype in data:
        cursor.execute("""
        INSERT OR REPLACE INTO talent_archetypes (
        id, name, description, weight, stat_modifiers_json,
        max_scene_partners_json, concurrency_limits_json,
        dynamic_preference_weights_json, trait_weights_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
        archetype.get('id'),
        archetype.get('name'),
        archetype.get('description'),
        archetype.get('weight'),
        json.dumps(archetype.get('stat_modifiers', {})),
        json.dumps(archetype.get('max_scene_partners', 10)),
        json.dumps(archetype.get('concurrency_limits', {})),
        json.dumps(archetype.get('dynamic_preference_weights', {})),
        json.dumps(archetype.get('trait_weights', {}))
        ))
        count += 1
    print(f"{count} talent archetype entries migrated.")

def migrate_traits(cursor, data):
    print("Migrating traits.json...")
    count = 0
    for trait in data:
        cursor.execute("""
        INSERT OR REPLACE INTO traits (
            id, name, description, type, modifiers_json, conflicts_with_json,
            policy_requirements_json, action_preference_modifiers_json,
            thematic_preference_modifiers_json, concurrency_modifiers_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trait.get('id'),
            trait.get('name'),
            trait.get('description'),
            trait.get('type'),
            json.dumps(trait.get('modifiers', {})),
            json.dumps(trait.get('conflicts_with', [])),
            json.dumps(trait.get('policy_requirements', {})),
            json.dumps(trait.get('action_preference_modifiers', {})),
            json.dumps(trait.get('thematic_preference_modifiers', {})),
            json.dumps(trait.get('concurrency_modifiers', {}))
        ))
        count += 1
    print(f"{count} trait entries migrated.")

def migrate_accommodation_tiers(cursor, data):
    print("Migrating accommodation_tiers.json...")
    count = 0
    for tier in data:
        cursor.execute("""
        INSERT OR REPLACE INTO accommodation_tiers (
            id, name, cost_per_week, pickiness_requirement, description
        ) VALUES (?, ?, ?, ?, ?)
        """, (
            tier.get('id'),
            tier.get('name'),
            tier.get('cost_per_week'),
            tier.get('pickiness_requirement'),
            tier.get('description')
        ))
        count += 1
    print(f"{count} accommodation tier entries migrated.")

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
        
        migrate_production_departments(cursor, load_json("production/production_departments.json"))
        migrate_visual_styles(cursor, load_json("production/visual_styles.json"))
        migrate_production_jobs(cursor, load_json("production/production_jobs.json"))
        migrate_production_locations(cursor, load_json("production/production_locations.json"))
        migrate_picture_set_types(cursor, load_json("production/picture_set_types.json"))
        
        migrate_post_production_settings(cursor, load_json("post_production_settings.json"))
        migrate_on_set_policies(cursor, load_json("studio_policies.json"))
        migrate_scene_events(cursor, load_json("events/scene_events.json"))
        migrate_talent_archetypes(cursor, load_json("talent_generation/talent_archetypes.json"))
        migrate_traits(cursor, load_json("talent_generation/traits.json"))
        migrate_accommodation_tiers(cursor, load_json("accommodation_tiers.json"))

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