import copy
from typing import Dict, List
from data.data_manager import DataManager
from database.db_models import MarketGroupStateDB
from data.game_state import MarketGroupState

class MarketService:
    def __init__(self, db_session, data_manager: DataManager):
        self.session = db_session
        self.data_manager = data_manager

    def get_all_market_states(self) -> Dict[str, MarketGroupState]:
        """Fetches all market group dynamic states from the database."""
        results = self.session.query(MarketGroupStateDB).all()
        return {r.name: r.to_dataclass(MarketGroupState) for r in results}

    def recover_all_market_saturation(self) -> bool:
        recovery_rate = self.data_manager.game_config.get("market_saturation_recovery_rate", 0.05)
        market_changed = False
        
        market_groups_db = self.session.query(MarketGroupStateDB).all()

        for group_db in market_groups_db:
            if group_db.current_saturation < 1.0:
                saturation_deficit = 1.0 - group_db.current_saturation
                recovery_amount = saturation_deficit * recovery_rate
                group_db.current_saturation = min(1.0, group_db.current_saturation + recovery_amount)
                market_changed = True
        
        return market_changed
    
    def get_resolved_group_data(self, group_name: str) -> Dict:
        all_groups = {g['name']: g for g in self.data_manager.market_data.get('viewer_groups', [])}
        group_data = all_groups.get(group_name)
        if not group_data or not group_data.get('inherits_from'): return group_data or {}
        
        parent_data = all_groups.get(group_data['inherits_from'])
        if not parent_data: return group_data
        
        resolved_data = copy.deepcopy(parent_data)
        for key, value in group_data.items():
            if key not in ['preferences', 'popularity_spillover']:
                resolved_data[key] = value

        if group_prefs := group_data.get('preferences'):
            resolved_prefs = resolved_data.setdefault('preferences', {})
            for pref_key, pref_values in group_prefs.items():
                resolved_prefs.setdefault(pref_key, {}).update(pref_values)
                
        if group_spillover := group_data.get('popularity_spillover'):
            resolved_data.setdefault('popularity_spillover', {}).update(group_spillover)
            
        return resolved_data