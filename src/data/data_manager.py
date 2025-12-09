import sqlite3
import json
import logging
from typing import Dict, Any, List
from collections import defaultdict, OrderedDict

from data.builders.action_tag_builder import ActionTagBuilder
from data.builders.physical_ethnicity_tag_builder import PhysicalEthnicityTagBuilder
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
        # Generator data must be loaded before tags to provide ethnicity hierarchy for tag generation
        self.generator_data = self._load_generator_data()
        self.tag_definitions = self._load_scene_tags()
        self.market_data = self._load_market_data()
        self.affinity_data = self._load_talent_affinities()
        self.production_departments = self._load_production_departments()
        self.visual_styles = self._load_visual_styles()
        self.production_jobs = self._load_production_jobs()
        self.production_locations = self._load_production_locations()
        self.picture_set_types = self._load_picture_set_types()
        self.post_production_data = self._load_post_production_data()
        self.studio_policies_data = self._load_studio_policies()
        self.scene_events = self._load_scene_events()
        self.talent_archetypes = self._load_talent_archetypes()
        self.traits_data = self._load_traits()
        self.help_topics = self._load_help_topics(help_file_path)
        self.accommodation_tiers = self._load_accommodation_tiers()
        self.travel_matrix = self._load_travel_matrix()
        self.ai_studio_archetypes = self._load_ai_studio_archetypes()
        
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
            
            # Check if this is an orientation template
            if tag_data.get('orientation') == 'Template':
                # Expand the template into concrete tags
                concrete_tags = ActionTagBuilder.expand_template(tag_data)
                
                for concrete_tag in concrete_tags:
                    base_name = concrete_tag.get('name')
                    orientation = concrete_tag.get('orientation')
                    
                    # Construct the full unique key (e.g., "Blowjob (Straight)")
                    # Note: For solo tags like "Masturbation (Male)", this format holds.
                    full_name = f"{base_name} ({orientation})" if orientation else base_name
                    
                    # Store full_name inside the dict for UI convenience if not already there
                    concrete_tag['full_name'] = full_name
                    tags[full_name] = concrete_tag
            else:
                # Legacy behavior for non-template tags
                base_name = tag_data.get('name')
                orientation = tag_data.get('orientation')
                full_name = f"{base_name} ({orientation})" if orientation else base_name
                
                tag_data['full_name'] = full_name
                tags[full_name] = tag_data

        # --- Dynamic Ethnicity Tag Generation ---
        try:
            hierarchy = self.get_ethnicity_hierarchy()
            # Only proceed if hierarchy exists (generator_data loaded successfully)
            if hierarchy:
                builder = PhysicalEthnicityTagBuilder(hierarchy, self.game_config)
                generated_tags = builder.generate_all_tags()
                
                for tag in generated_tags:
                    base_name = tag.get('name')
                    orientation = tag.get('orientation')
                    
                    # Determine full unique key using same logic as legacy tags
                    # e.g. "White" (orientation="Male") -> "White (Male)"
                    # e.g. "Ebony" (orientation="Female") -> "Ebony (Female)"
                    # e.g. "Interracial (BM/WF)" (orientation=None) -> "Interracial (BM/WF)"
                    full_name = f"{base_name} ({orientation})" if orientation else base_name
                    
                    tag['full_name'] = full_name
                    
                    # Add to tags map if not already defined in database/JSON
                    # This allows JSON files to override code-generated defaults (e.g. for BBC)
                    if full_name not in tags:
                        tags[full_name] = tag
                        
        except Exception as e:
            logger.error(f"Failed to generate dynamic ethnicity tags: {e}")
                
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
        """Loads all data related to talent generation from multiple tables."""
        cursor = self.conn.cursor()
        data = defaultdict(dict)
        
        cursor.execute("SELECT category, name, weight FROM generation_weights")
        for row in cursor.fetchall():
            category = row['category']
            if category not in data:
                data[category] = []
            data[category].append({"name": row['name'], "weight": row['weight']})
        
        # Hierarchical ethnicity definitions
        cursor.execute("SELECT name, primary_ethnicity FROM ethnicity_definitions")
        data['ethnicity_definitions'] = {row['name']: row['primary_ethnicity'] for row in cursor.fetchall()}
        # For UI/logic lookups, create the inverse mapping too
        primary_to_sub = defaultdict(list)
        for sub, prim in data['ethnicity_definitions'].items():
            if sub != prim: # Don't add primary as its own sub
                primary_to_sub[prim].append(sub)
        data['primary_ethnicities'] = {k: v for k, v in primary_to_sub.items()}

        # Create a full hierarchy map (including primaries with no subs)
        # This is used for building UIs like tree views.
        all_primary_groups = sorted(list(set(data['ethnicity_definitions'].values())))
        hierarchy = OrderedDict()
        for primary_group in all_primary_groups:
            # Get subs if they exist, otherwise it's an empty list
            hierarchy[primary_group] = sorted(data['primary_ethnicities'].get(primary_group, []))
        data['ethnicity_hierarchy'] = hierarchy
        
        # Nationality data
        cursor.execute("SELECT name, weight FROM nationalities")
        data['nationalities'] = [dict(row) for row in cursor.fetchall()]

        cursor.execute("SELECT nationality_name, location_name, weight FROM nationality_locations")
        for row in cursor.fetchall():
            nat = row['nationality_name']
            if nat not in data['locations_by_nationality']:
                data['locations_by_nationality'][nat] = []
            data['locations_by_nationality'][nat].append({'name': row['location_name'], 'weight': row['weight']})

        cursor.execute("SELECT nationality_name, ethnicity_name, weight FROM nationality_ethnicities")
        for row in cursor.fetchall():
            nat = row['nationality_name']
            if nat not in data['ethnicities_by_nationality']:
                data['ethnicities_by_nationality'][nat] = []
            data['ethnicities_by_nationality'][nat].append({'name': row['ethnicity_name'], 'weight': row['weight']})
            
        # Cultural names
        cursor.execute("SELECT culture_key, gender, part, name FROM cultural_names")
        for row in cursor.fetchall():
            key, gender, part, name = row['culture_key'], row['gender'], row['part'], row['name']
            if key not in data['names_by_culture']:
                data['names_by_culture'][key] = defaultdict(lambda: defaultdict(list))
            data['names_by_culture'][key][gender][part].append(name)
        
        # Regions
        cursor.execute("SELECT region_name, location_name FROM region_locations")
        data['location_to_region'] = {row['location_name']: row['region_name'] for row in cursor.fetchall()}

        # Convert defaultdicts to regular dicts for cleaner access
        return json.loads(json.dumps(data))

    def _load_travel_matrix(self) -> Dict[str, Dict[str, Dict[str, int]]]:
        """Loads the region-to-region travel costs into a nested dictionary for fast lookups."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT origin_region, destination_region, cost, fatigue FROM region_travel_costs")
        rows = cursor.fetchall()
        matrix = defaultdict(dict)
        for row in rows:
            origin = row['origin_region']
            destination = row['destination_region']
            matrix[origin][destination] = {
                'cost': row['cost'],
                'fatigue': row['fatigue']
            }
        logger.info(f"Loaded {len(rows)} travel cost entries into matrix.")
        return dict(matrix)

    def _load_production_departments(self) -> Dict[str, Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM production_departments")
        departments = {}
        for row in cursor.fetchall():
            data = self._rehydrate_json_fields(dict(row))
            if 'id' in data:
                departments[data['id']] = data
        return departments

    def _load_visual_styles(self) -> Dict[str, Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM visual_styles")
        styles = {}
        for row in cursor.fetchall():
            data = self._rehydrate_json_fields(dict(row))
            if 'id' in data:
                styles[data['id']] = data
        return styles

    def _load_production_jobs(self) -> Dict[str, Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM production_jobs")
        jobs = {}
        for row in cursor.fetchall():
            data = dict(row)
            if 'id' in data:
                jobs[data['id']] = data
        return jobs

    def _load_production_locations(self) -> Dict[str, Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM production_locations")
        locations = {}
        for row in cursor.fetchall():
            data = self._rehydrate_json_fields(dict(row))
            if 'id' in data:
                locations[data['id']] = data
        return locations

    def _load_picture_set_types(self) -> Dict[str, Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM picture_set_types")
        pst = {}
        for row in cursor.fetchall():
            data = dict(row)
            if 'id' in data:
                pst[data['id']] = data
        return pst

    def _load_post_production_data(self) -> Dict[str, List[Dict]]:
        """Loads all post-production editing tiers from the database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM post_production_definitions ORDER BY cost")
        
        tiers = []
        for row in cursor.fetchall():
            tier_data = self._rehydrate_json_fields(dict(row))
            tiers.append(tier_data)
            
        return {"editing_tiers": tiers}

    def _load_studio_policies(self) -> Dict[str, Dict]:
        """Loads all studio policy definitions from the database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, description, per_scene_cost, weekly_upkeep FROM studio_policy_definitions ORDER BY name")
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
                # Inject 'type' so archetypes can be treated like traits in UI/Logic
                archetype_data['type'] = 'archetype'
                archetypes[archetype_id] = archetype_data
        return archetypes

    def _load_traits(self) -> Dict[str, Dict]:
        """Loads all trait definitions from the database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM traits")
        traits = {}
        for row in cursor.fetchall():
            trait_data = self._rehydrate_json_fields(dict(row))
            trait_id = trait_data.get('id')
            if trait_id:
                traits[trait_id] = trait_data
        return traits
    
    def _load_accommodation_tiers(self) -> Dict[str, Dict]:
        """Loads all accommodation tier definitions from the database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM accommodation_tiers ORDER BY cost_per_week")
        tiers = {}
        for row in cursor.fetchall():
            tier_data = dict(row)
            tier_id = tier_data.get('id')
            if tier_id:
                tiers[tier_id] = tier_data
        return tiers

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
        
    def _load_ai_studio_archetypes(self) -> List[Dict[str, Any]]:
        """Loads AI studio archetypes from the SQLite database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM ai_studio_archetypes")
        archetypes = []
        for row in cursor.fetchall():
            data = self._rehydrate_json_fields(dict(row))
            archetypes.append(data)
        return archetypes
    
    def get_available_ethnicities(self) -> List[str]:
        """Returns a sorted list of primary ethnicity groups."""
        if not self.generator_data: return []
        return sorted(list(self.generator_data.get('ethnicity_definitions', {}).keys()))

    def get_ethnicity_hierarchy(self) -> Dict[str, List[str]]:
        """Returns a dictionary mapping primary ethnicities to their sub-groups."""
        if not self.generator_data: return {}
        return self.generator_data.get('ethnicity_hierarchy', {})
    
    def is_ethnicity_match(self, specific_ethnicity: str, required_ethnicity: str) -> bool:
        """
        Checks if a specific ethnicity satisfies a requirement, supporting primary group hierarchy.
        e.g., is_ethnicity_match('Western European', 'White') -> True
        """
        if not specific_ethnicity or not required_ethnicity:
            return False

        # An ethnicity always satisfies a requirement for itself.
        if specific_ethnicity == required_ethnicity:
            return True

        # Check for hierarchical match (e.g., specific is 'Western European', requirement is 'White')
        primary_to_sub_map = self.generator_data.get('primary_ethnicities', {})
        
        # Is the requirement a primary group with sub-groups?
        if required_ethnicity in primary_to_sub_map:
            # If so, is the specific ethnicity one of those sub-groups?
            if specific_ethnicity in primary_to_sub_map[required_ethnicity]:
                return True
            
        return False

    def get_available_cup_sizes(self) -> List[str]:
        return [c['name'] for c in self.generator_data.get('cup_sizes', [])]
    
    def get_available_nationalities(self) -> List[str]:
        """Returns a sorted list of all available nationality names."""
        if not self.generator_data: return []
        nationalities = self.generator_data.get('nationalities', [])
        return sorted([nat['name'] for nat in nationalities])

    def get_location_to_region_map(self) -> Dict[str, str]:
        """Returns a direct mapping of location name to its region name."""
        if not self.generator_data: return {}
        return self.generator_data.get('location_to_region', {})

    def get_locations_by_region(self) -> Dict[str, List[str]]:
        """Returns a dictionary mapping regions to a sorted list of their locations."""
        # Define a specific order to override alphabetical sorting for UI purposes.
        region_order = [
            "North America",
            "South America",
            "British Isles",
            "Western Europe",
            "Eastern Europe",
            "East Asia"
        ]
        location_map = self.get_location_to_region_map()
        regions_map = defaultdict(list)
        for location, region in location_map.items():
            regions_map[region].append(location)
        # Build the final dictionary respecting the predefined order.
        ordered_regions = OrderedDict()
        for region in region_order:
            if region in regions_map:
                ordered_regions[region] = sorted(regions_map[region])
        return ordered_regions

    def get_trait_definition(self, trait_id: str) -> Dict[str, Any]:
        """
        Retrieves a trait definition by ID. 
        Also checks archetypes if the ID is not found in standard traits,
        allowing for polymorphic display.
        """
        if trait_id in self.traits_data:
            return self.traits_data[trait_id]
        if trait_id in self.talent_archetypes:
            return self.talent_archetypes[trait_id]
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