import copy
from typing import Dict

class MarketGroupResolver:
    """
    Handles the resolution of inheritance for static market group data.
    This class is pure logic and has no database dependencies.
    """
    def __init__(self, market_data: dict):
        self.all_groups = {g['name']: g for g in market_data.get('viewer_groups', [])}
        self._resolved_cache = self._pre_resolve_all_groups()

    def _pre_resolve_all_groups(self) -> Dict[str, Dict]:
        """Resolves inheritance for all viewer groups once and caches them."""
        resolved_cache = {}
        for group_name in self.all_groups:
            if group_name not in resolved_cache: # Avoid re-processing
                resolved_cache[group_name] = self._resolve_single_group(group_name, set())
        return resolved_cache

    def _resolve_single_group(self, group_name: str, processing_stack: set) -> Dict:
        """Recursive helper to resolve inheritance for one group."""
        if group_name in processing_stack:
            raise RecursionError(f"Circular inheritance detected for market group: {group_name}")
        
        # Check cache first
        if group_name in getattr(self, '_resolved_cache', {}):
            return self._resolved_cache[group_name]

        group_data = self.all_groups.get(group_name, {})
        if not (parent_name := group_data.get('inherits_from')):
            return group_data

        processing_stack.add(group_name)
        parent_data = self._resolve_single_group(parent_name, processing_stack)
        processing_stack.remove(group_name)
        
        resolved_data = copy.deepcopy(parent_data)
        
        # Merge child data into parent data
        for key, value in group_data.items():
            if key not in ['preferences', 'popularity_spillover', 'inherits_from']:
                resolved_data[key] = value

        if group_prefs := group_data.get('preferences'):
            resolved_prefs = resolved_data.setdefault('preferences', {})
            for pref_key, pref_values in group_prefs.items():
                resolved_prefs.setdefault(pref_key, {}).update(pref_values)
                
        if group_spillover := group_data.get('popularity_spillover'):
            resolved_data.setdefault('popularity_spillover', {}).update(group_spillover)
            
        return resolved_data

    def get_resolved_group(self, group_name: str) -> Dict:
        """Public method to safely get resolved data from the cache."""
        return self._resolved_cache.get(group_name, {})
    
    def get_all_resolved_groups(self) -> Dict[str, Dict]:
        """Public method to safely get all resolved data from the cache."""
        return self._resolved_cache