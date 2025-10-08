import sqlite3
import json
from typing import Dict, Any, List
import os 
from collections import defaultdict

try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(script_dir, "data", "game_data.sqlite")
except NameError:
    DB_PATH = os.path.join("data", "game_data.sqlite")

class DataManager:
    """
    Handles loading all static game data from the SQLite database at startup.
    This class is instantiated once and passed to the controller.
    """
    def __init__(self, db_path: str = DB_PATH):
        self.conn = None
        
        try:
            self.conn = sqlite3.connect(db_path)
            self.conn.row_factory = sqlite3.Row # Allows accessing columns by name
        except sqlite3.OperationalError as e:
            print(f"FATAL: Could not connect to database at '{db_path}'.")
            print("Please ensure 'game_data.sqlite' exists in the 'data' folder and that the migration script has been run.")
            raise e

        # Load all data into memory on initialization
        self.game_config = self._load_game_config()
        self.tag_definitions = self._load_scene_tags()
        self.market_data = self._load_market_data()
        self.affinity_data = self._load_talent_affinities()
        self.generator_data = self._load_generator_data()
        self.production_settings_data = self._load_production_settings()
        self.post_production_data = self._load_post_production_data()
        self.on_set_policies_data = self._load_on_set_policies()
        self.scene_events = self._load_scene_events()
        self.talent_archetypes = self._load_talent_archetypes()

    def _rehydrate_json_fields(self, data_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Finds keys ending in '_json', loads their string content as JSON,
        and replaces them with a key without the suffix.
        """
        hydrated_dict = data_dict.copy()
        
        for key in list(hydrated_dict.keys()):
            if key.endswith('_json'):
                value = hydrated_dict[key]
                new_key = key[:-5]
                
                hydrated_dict[new_key] = json.loads(value) if value else None
                
                del hydrated_dict[key]
            
        return hydrated_dict


    def _load_game_config(self) -> Dict[str, Any]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT key, value FROM game_config")
        config = {}
        for row in cursor.fetchall():
            try:
                # Attempt to parse as JSON first (for lists/dicts)
                config[row['key']] = json.loads(row['value'])
            except (json.JSONDecodeError, TypeError):
                # Fallback to float, int, or string
                val = row['value']
                try:
                    if '.' in val: config[row['key']] = float(val)
                    else: config[row['key']] = int(val)
                except (ValueError, TypeError):
                    config[row['key']] = val
        return config

    def _load_scene_tags(self) -> Dict[str, Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM scene_tags")
        tags = {}
        for row in cursor.fetchall():
            tag_data = self._rehydrate_json_fields(dict(row))
            base_name = tag_data.get('name')
            orientation = tag_data.get('orientation')
            full_name = f"{base_name} ({orientation})" if orientation else base_name
            tags[full_name] = tag_data
        return tags

    def _load_market_data(self) -> Dict[str, Any]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM viewer_groups")
        groups = []
        for row in cursor.fetchall():
            group_data = self._rehydrate_json_fields(dict(row))
            groups.append(group_data)
        return {"viewer_groups": groups}

    def _load_talent_affinities(self) -> Dict[str, Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT category, name, data_json FROM talent_affinities")
        
        affinities = defaultdict(dict)
        
        for row in cursor.fetchall():
            category = row['category']
            name = row['name']
            data = json.loads(row['data_json']) if row['data_json'] else {}
            
            # FIX: Handle the special structure of DickSize data.
            # Instead of nesting it under a 'default' key, assign it directly
            # to the 'DickSize' category key.
            if category == "DickSize":
                affinities[category] = data
            else:
                affinities[category][name] = data
            
        return dict(affinities)

    def _load_generator_data(self) -> Dict[str, Any]:
        cursor = self.conn.cursor()
        data = {}
        
        # Load weights (this part is unchanged and correct)
        cursor.execute("SELECT category, name, weight FROM generation_weights")
        for row in cursor.fetchall():
            category = row['category']
            if category not in data:
                data[category] = []
            data[category].append({"name": row['name'], "weight": row['weight']})
        
        # Load aliases from the new `talent_aliases` table
        # We use defaultdict to make building the nested structure easier
        aliases = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        cursor.execute("SELECT ethnicity, gender, part, name FROM talent_aliases")
        for row in cursor.fetchall():
            aliases[row['ethnicity']][row['gender']][row['part']].append(row['name'])
            
        # Convert the defaultdicts to regular dicts for a clean final object
        # and assign it to the 'aliases' key in our main data dictionary.
        data['aliases'] = json.loads(json.dumps(aliases))
            
        return data
    
    def _load_production_settings(self) -> Dict[str, List[Dict]]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT category, tier_name, cost_per_scene, cost_multiplier, quality_modifier, description,
                   bad_event_chance_modifier, good_event_chance_modifier
            FROM production_settings_definitions 
            ORDER BY category, cost_per_scene, cost_multiplier
        """)
        
        settings = {}
        for row in cursor.fetchall():
            category = row['category']
            if category not in settings:
                settings[category] = []
            
            settings[category].append(dict(row))
        return settings

    def _load_post_production_data(self) -> Dict[str, List[Dict]]:
        """Loads all post-production editing tiers from the database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM post_production_definitions ORDER BY cost")
        
        tiers = []
        for row in cursor.fetchall():
            tier_data = self._rehydrate_json_fields(dict(row))
            tiers.append(tier_data)
            
        return {"editing_tiers": tiers}

    def _load_on_set_policies(self) -> Dict[str, Dict]:
        """Loads all on-set policy definitions from the database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, description, cost_per_bloc FROM on_set_policies_definitions ORDER BY name")
        policies = {}
        for row in cursor.fetchall():
            policy_data = dict(row)
            policy_id = policy_data.get('id')
            if policy_id:
                policies[policy_id] = policy_data
        return policies

    def _load_scene_events(self) -> Dict[str, Dict]:
        """Loads all scene event definitions from the database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM scene_events")
        events = {}
        for row in cursor.fetchall():
            event_data = self._rehydrate_json_fields(dict(row))
            event_id = event_data.get('id')
            if event_id:
                events[event_id] = event_data
        return events
    
    def _load_talent_archetypes(self) -> Dict[str, Dict]:
        """Loads all talent archetype definitions from the database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM talent_archetypes")
        archetypes = {}
        for row in cursor.fetchall():
            archetype_data = self._rehydrate_json_fields(dict(row))
            archetype_id = archetype_data.get('id')
            if archetype_id:
                archetypes[archetype_id] = archetype_data
        return archetypes

    def close(self):
        """Explicitly close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __del__(self):
        """Ensure the database connection is closed when the object is destroyed."""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()