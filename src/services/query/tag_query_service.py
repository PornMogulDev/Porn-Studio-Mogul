
from typing import List, Dict, Set, Tuple, Optional

from data.data_manager import DataManager

class TagQueryService:
    """A read-only service for querying and formatting static tag data for the UI."""
    def __init__(self, data_manager: DataManager):
        self.tag_definitions = data_manager.tag_definitions
        self._cached_data = {}

    def get_tags_for_planner(self, tag_type: str) -> Tuple[List[Dict], Set[str], Set[str]]:
        """
        Gets and processes tags of a specific type for the scene planner UI.
        Caches the result after the first call.
        """
        if tag_type in self._cached_data:
            return self._cached_data[tag_type]

        tags, categories, orientations = [], set(), set()
        for full_name, tag_data in self.tag_definitions.items():
            if tag_data.get('type') == tag_type:
                cats_raw = tag_data.get('categories', [])
                cats = [cats_raw] if isinstance(cats_raw, str) else cats_raw
                categories.update(cats)
                
                if orientation := tag_data.get('orientation'):
                    orientations.add(orientation)
                
                tag_data_with_name = tag_data.copy()
                tag_data_with_name['full_name'] = full_name

                # Special handling for Action tags
                if tag_type == 'Action':
                    count = sum(slot.get('count', slot.get('min_count', 0)) for slot in tag_data.get('slots', []))
                    tag_data_with_name['participant_count'] = count

                tags.append(tag_data_with_name)
        
        result = (tags, categories, orientations)
        self._cached_data[tag_type] = result
        return result
    
    def get_tag_definition(self, tag_name: str) -> Optional[Dict]:
        """Fetches a single tag definition dictionary by its name."""
        return self.tag_definitions.get(tag_name)