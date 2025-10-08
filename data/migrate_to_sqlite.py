import sqlite3
import json
import os

DB_FILE = "game_data.sqlite"

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
    # This table replaces the old generation_aliases table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS talent_aliases (
        ethnicity TEXT NOT NULL,
        gender TEXT NOT NULL,
        part TEXT NOT NULL, -- 'first', 'last', or 'single'
        name TEXT NOT NULL,
        PRIMARY KEY (ethnicity, gender, part, name)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS talent_affinities (
        gender TEXT NOT NULL,
        affinity_name TEXT NOT NULL,
        age_points_json TEXT NOT NULL,
        values_json TEXT NOT NULL,
        PRIMARY KEY (gender, affinity_name)
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
        quality_source_json TEXT,
        revenue_weights_json TEXT,
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

    # NEW: post_production_settings
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
        preferences_json TEXT,
        hard_limits_json TEXT,
        stat_modifiers_json TEXT
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
    count = 0
    for category_name in ["genders", "ethnicities", "physiques", "boob_cups"]:
        if category_name in data:
            for item in data[category_name]:
                cursor.execute("INSERT OR REPLACE INTO generation_weights (category, name, weight) VALUES (?, ?, ?)",
                               (category_name, item['name'], item['weight']))
                count += 1
    print(f"{count} talent generation weight entries migrated.")

def migrate_aliases(cursor, data):
    """Migrates the structured aliases from JSON into the talent_aliases table."""
    print("Migrating aliases_structured.json...")
    count = 0
    for ethnicity, genders in data.items():
        for gender, parts in genders.items():
            for part, names in parts.items():
                for name in names:
                    cursor.execute("""
                        INSERT OR REPLACE INTO talent_aliases (ethnicity, gender, part, name)
                        VALUES (?, ?, ?, ?)
                    """, (ethnicity, gender, part, name))
                    count += 1
    print(f"{count} alias entries migrated.")

def migrate_talent_affinities(cursor, data):
    print("Migrating talent_affinity_data.json...")
    count = 0
    for gender, affinities in data.items():
        for affinity_name, details in affinities.items():
            age_points_str = json.dumps(details['age_points'])
            values_str = json.dumps(details['values'])
            cursor.execute("""
                INSERT OR REPLACE INTO talent_affinities (gender, affinity_name, age_points_json, values_json)
                VALUES (?, ?, ?, ?)
            """, (gender, affinity_name, age_points_str, values_str))
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


def migrate_scene_tags(cursor, data):
    print("Migrating scene_tags.json...")
    count = 0
    for tag in data:
        is_template = 1 if tag.get('is_template', False) else 0
        is_auto_taggable = 1 if tag.get('is_auto_taggable', False) else 0
        appeal_weight = tag.get('appeal_weight') or 10.0

        cursor.execute("""
            INSERT OR REPLACE INTO scene_tags (
                name, orientation, type, concept, is_template, is_auto_taggable, 
                categories_json, slots_json, expands_to_json, validation_rule_json,
                quality_source_json, revenue_weights_json, ethnicity,
                gender, tooltip, appeal_weight
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tag.get('name'), tag.get('orientation'), tag.get('type'), tag.get('concept'),
            is_template, is_auto_taggable, json.dumps(tag.get('categories')), 
            json.dumps(tag.get('slots')), json.dumps(tag.get('expands_to')), 
            json.dumps(tag.get('validation_rule')), json.dumps(tag.get('quality_source')), 
            json.dumps(tag.get('revenue_weights')), tag.get('ethnicity'), 
            tag.get('gender'), tag.get('tooltip'), appeal_weight
        ))
        count += 1
    print(f"{count} scene tags migrated.")

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
                id, name, description, weight, preferences_json,
                hard_limits_json, stat_modifiers_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            archetype.get('id'),
            archetype.get('name'),
            archetype.get('description'),
            archetype.get('weight'),
            json.dumps(archetype.get('preferences', {})),
            json.dumps(archetype.get('hard_limits', [])),
            json.dumps(archetype.get('stat_modifiers', {}))
        ))
        count += 1
    print(f"{count} talent archetype entries migrated.")

def main():
    """Main function to run the entire migration process."""
    if os.path.exists(DB_FILE):
        print(f"'{DB_FILE}' already exists. Deleting to start fresh.")
        os.remove(DB_FILE)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    create_tables(cursor)

    # Load JSON files and run migrations
    try:
        with open("game_config.json", "r") as f:
            migrate_config(cursor, json.load(f))

        with open("talent_generation_data.json", "r") as f:
            migrate_talent_generation(cursor, json.load(f))

        with open("aliases_structured.json", "r") as f:
            migrate_aliases(cursor, json.load(f))

        with open("talent_affinity_data.json", "r") as f:
            migrate_talent_affinities(cursor, json.load(f))

        with open("market.json", "r") as f:
            migrate_market(cursor, json.load(f))

        with open("scene_tags.json", "r") as f:
            migrate_scene_tags(cursor, json.load(f))

        with open("production_settings.json", "r") as f:
            migrate_production_settings(cursor, json.load(f))

        with open("post_production_settings.json", "r") as f:
            migrate_post_production_settings(cursor, json.load(f))

        with open("on_set_policies.json", "r") as f:
            migrate_on_set_policies(cursor, json.load(f))

        with open("scene_events.json", "r") as f:
            migrate_scene_events(cursor, json.load(f))

        with open("talent_archetypes.json", "r") as f:
            migrate_talent_archetypes(cursor, json.load(f))

    except FileNotFoundError as e:
        print(f"ERROR: Missing data file '{e.filename}'. Cannot continue migration.")
        conn.rollback()
    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    else:
        print("\nMigration completed successfully!")
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()