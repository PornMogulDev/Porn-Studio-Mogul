import sqlite3
import json
import logging
from typing import Dict, Any, List
from collections import defaultdict

from utils.paths import GAME_DATA, HELP_FILE

# Set up a logger for this module
logger = logging.getLogger(__name__)

class DataManager:
    """
    Handles loading all static game data from the SQLite database at startup.
    This class is instantiated once and passed to the controller.
    """
    def __init__(self, db_path: str = GAME_DATA, help_file_path: str = HELP_FILE):
        self.conn = None
        
        try:
            self.conn = sqlite3.connect(db_path)
            self.conn.row_factory = sqlite3.Row # Allows accessing columns by name
            logger.info(f"Successfully connected to database: {db_path}")
        except sqlite3.OperationalError as e:
            logger.critical(f"FATAL: Could not connect to database at '{db_path}'.")
            logger.critical("Please ensure 'game_data.sqlite' exists in the 'data' folder and that the migration script has been run.")
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
        self.help_topics = self._load_help_topics(help_file_path)
        
        logger.info("All game data loaded into memory.")

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
            
            # Handle the special structure of DickSize data.
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
        
        cursor.execute("SELECT category, name, weight FROM generation_weights")
        for row in cursor.fetchall():
            category = row['category']
            if category not in data:
                data[category] = []
            data[category].append({"name": row['name'], "weight": row['weight']})
        
        aliases = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        cursor.execute("SELECT ethnicity, gender, part, name FROM talent_aliases")
        for row in cursor.fetchall():
            aliases[row['ethnicity']][row['gender']][row['part']].append(row['name'])
            
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

    def _load_help_topics(self, file_path: str) -> Dict[str, Any]:
        """Loads help topic data from a JSON file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Help topics file not found at '{file_path}'. Help feature will fail when trying to access it.")
            return {}
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse help topics file at '{file_path}'. It may be malformed.")
            return {}

    def close(self):
        """Explicitly close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Database connection closed.")

    def __del__(self):
        """Ensure the database connection is closed when the object is destroyed."""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()