import logging
import random
from collections import defaultdict
from typing import Dict, List
from sqlalchemy.orm import Session

from database.db_models import MarketGroupStateDB
from data.game_state import MarketGroupState, Scene

logger = logging.getLogger(__name__)

class MarketService:
    def __init__(self, market_group_resolver, tag_definitions: dict, config):
        self.resolver = market_group_resolver
        self.tag_definitions = tag_definitions
        self.config = config

    def recover_all_market_saturation(self, session: Session) -> bool:
        market_changed = False
        market_groups_db = session.query(MarketGroupStateDB).all()
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
    
    def process_discoveries_from_release(
        self,
        session: Session,
        scene: Scene,
        viewer_group_interest: Dict[str, float]
    ) -> Dict[str, List[str]]:
        """
        Processes market sentiment discoveries after a scene release.
        Operates within the caller's transaction.
        Returns a dictionary of newly discovered sentiments.
        """
        discovery_threshold = self.config.discovery_interest_threshold
        num_to_discover = self.config.discoveries_per_scene
        all_new_discoveries = defaultdict(list)

        for group_name, interest in viewer_group_interest.items():
            if interest < discovery_threshold:
                continue

            market_state_db = session.query(MarketGroupStateDB).get(group_name)
            if not market_state_db: continue

            potential_discoveries = self.get_potential_discoveries(scene, group_name)
            current_discovered = market_state_db.discovered_sentiments
            newly_discovered_count = 0

            random.shuffle(potential_discoveries)
            potential_discoveries.sort(key=lambda x: x['impact'], reverse=True)

            for item in potential_discoveries:
                if newly_discovered_count >= num_to_discover: break
                sentiment_type, tag_name = item['type'], item['tag']

                if tag_name not in current_discovered.get(sentiment_type, []):
                    current_discovered.setdefault(sentiment_type, []).append(tag_name)
                    all_new_discoveries[group_name].append(tag_name)
                    newly_discovered_count += 1

        return dict(all_new_discoveries)

    def update_saturation_from_release(
        self,
        session: Session,
        market_saturation_updates: Dict[str, float]
    ):
        """Updates market saturation based on release results. Operates within the caller's transaction."""
        for group_name, cost in market_saturation_updates.items():
            market_state_db = session.query(MarketGroupStateDB).get(group_name)
            if market_state_db:
                market_state_db.current_saturation = max(0, market_state_db.current_saturation - cost)