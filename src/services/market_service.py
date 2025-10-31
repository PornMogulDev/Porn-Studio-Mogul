import logging
import copy
from typing import Dict, List

from database.db_models import MarketGroupStateDB
from data.game_state import MarketGroupState, Scene

logger = logging.getLogger(__name__)

class MarketService:
    def __init__(self, db_session, market_data: dict, tag_definitions: dict):
        self.session = db_session
        self.market_data = market_data
        self.tag_definitions = tag_definitions
        self._resolved_groups_cache = self._pre_resolve_all_groups()

    def get_all_market_states(self) -> Dict[str, MarketGroupState]:
        """Fetches all market group dynamic states from the database."""
        results = self.session.query(MarketGroupStateDB).all()
        return {r.name: r.to_dataclass(MarketGroupState) for r in results}

    def recover_all_market_saturation(self) -> bool:
        recovery_rate = self.market_data.get("saturation_recovery_rate", 0.05)
        market_changed = False

        try:
            market_groups_db = self.session.query(MarketGroupStateDB).all()

            for group_db in market_groups_db:
                if group_db.current_saturation < 1.0:
                    saturation_deficit = 1.0 - group_db.current_saturation
                    recovery_amount = saturation_deficit * recovery_rate
                    group_db.current_saturation = min(1.0, group_db.current_saturation + recovery_amount)
                    market_changed = True
            
            if market_changed:
                self.session.commit()
        except Exception as e:
            logger.error(f"Error recovering market saturation: {e}", exc_info=True)
            return False
        
        return market_changed
    
    def _pre_resolve_all_groups(self) -> Dict[str, Dict]:
        """Resolves inheritance for all viewer groups once and caches them."""
        all_groups = {g['name']: g for g in self.market_data.get('viewer_groups', [])}
        resolved_cache = {}
        # Iterate in a way that ensures parents are processed before children, if possible.
        # A simple loop is fine if inheritance depth is low (e.g., 1 level).
        for group_name in all_groups:
            resolved_cache[group_name] = self._resolve_single_group(group_name, all_groups)
        return resolved_cache

    def _resolve_single_group(self, group_name: str, all_groups: Dict) -> Dict:
        """Recursive helper to resolve inheritance for one group."""
        group_data = all_groups.get(group_name, {})
        if not (parent_name := group_data.get('inherits_from')):
            return group_data

        # Recursively resolve the parent first.
        parent_data = self._resolve_single_group(parent_name, all_groups)
        
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
    
    def get_resolved_group_data(self, group_name: str) -> Dict:
        return self._resolved_groups_cache.get(group_name, {})
    
    def get_potential_discoveries(self, scene: Scene, group_name: str) -> List[Dict]:
        """Identifies sentiments that could be discovered from a successful scene."""
        # This is a simplified example. A full implementation would need to more
        # deeply analyze the revenue calculation to find the true top contributors.
        
        group_data = self.get_resolved_group_data(group_name)
        prefs = group_data.get('preferences', {})
        discoveries = []

        # Thematic Tags
        thematic_prefs = prefs.get('thematic_sentiments', {})
        for tag in scene.global_tags:
            if tag in thematic_prefs:
                discoveries.append({'type': 'thematic_sentiments', 'tag': tag, 'impact': abs(thematic_prefs[tag])})

        # Physical & Action Tags
        all_content_tags = set(scene.assigned_tags.keys()) | {seg.tag_name for seg in scene.action_segments}
        phys_prefs = prefs.get('physical_sentiments', {})
        act_prefs = prefs.get('action_sentiments', {})

        for tag in all_content_tags:
            tag_def = self.tag_definitions.get(tag, {})
            if tag_def.get('type') == 'Physical' and tag in phys_prefs:
                discoveries.append({'type': 'physical_sentiments', 'tag': tag, 'impact': abs(phys_prefs[tag] - 1.0)})
            elif tag_def.get('type') == 'Action' and tag in act_prefs:
                discoveries.append({'type': 'action_sentiments', 'tag': tag, 'impact': abs(act_prefs[tag] - 1.0)})

        return discoveries