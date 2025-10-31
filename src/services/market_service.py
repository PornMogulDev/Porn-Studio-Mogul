import logging
from typing import Dict, List

from database.db_models import MarketGroupStateDB
from data.game_state import MarketGroupState, Scene

logger = logging.getLogger(__name__)

class MarketService:
    def __init__(self, db_session, market_group_resolver, tag_definitions: dict, config):
        self.session = db_session
        self.resolver = market_group_resolver
        self.tag_definitions = tag_definitions
        self.config = config

    def get_all_market_states(self) -> Dict[str, MarketGroupState]:
        """Fetches all market group dynamic states from the database."""
        results = self.session.query(MarketGroupStateDB).all()
        return {r.name: r.to_dataclass(MarketGroupState) for r in results}

    def recover_all_market_saturation(self) -> bool:
        market_changed = False
        market_groups_db = self.session.query(MarketGroupStateDB).all()
        for group_db in market_groups_db:
            if group_db.current_saturation < 1.0:
                saturation_deficit = 1.0 - group_db.current_saturation
                recovery_amount = saturation_deficit * self.config.saturation_recovery_rate
                group_db.current_saturation = min(1.0, group_db.current_saturation + recovery_amount)
                market_changed = True
        
        return market_changed
    
    def get_resolved_group_data(self, group_name: str) -> Dict:
        return self.resolver.get_resolved_group(group_name)
    
    def get_all_resolved_group_data(self) -> Dict[str, Dict]:
        """Returns the fully resolved static data for all market groups."""
        return self.resolver.get_all_resolved_groups()
    
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
        all_content_tags = set(scene.assigned_tags.keys()) | {seg.tag for seg in scene.action_segments}
        phys_prefs = prefs.get('physical_sentiments', {})
        act_prefs = prefs.get('action_sentiments', {})

        for tag in all_content_tags:
            tag_def = self.tag_definitions.get(tag, {})
            if tag_def.get('type') == 'Physical' and tag in phys_prefs:
                discoveries.append({'type': 'physical_sentiments', 'tag': tag, 'impact': abs(phys_prefs[tag] - 1.0)})
            elif tag_def.get('type') == 'Action' and tag in act_prefs:
                discoveries.append({'type': 'action_sentiments', 'tag': tag, 'impact': abs(act_prefs[tag] - 1.0)})

        return discoveries