import json
import logging
from typing import List

from core.interfaces import GameSignals
from database.db_models import GameInfoDB

logger = logging.getLogger(__name__)

class PlayerSettingsService:
    """
    Manages player-specific settings that are persisted in the database,
    such as favorite tags.
    """
    def __init__(self, db_session, signals: GameSignals):
        self.session = db_session
        self.signals = signals
        self._cache = {} # Cache for storing loaded settings like favorites

    def clear_cache(self):
        """Clears the internal cache, forcing a reload from the DB on next access."""
        self._cache.clear()

    # --- Tag Favorites System ---

    def get_favorite_tags(self, tag_type: str) -> List[str]:
        """
        Fetches the list of favorite tags for a given type from the database.
        Results are cached for performance.
        """
        key = f"favorite_{tag_type}_tags"
        if key in self._cache:
            return self._cache[key]
        
        if not self.session: 
            return []
        
        fav_info = self.session.query(GameInfoDB).filter_by(key=key).first()
        if fav_info and fav_info.value:
            try:
                favs = json.loads(fav_info.value)
                self._cache[key] = favs
                return favs
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Could not parse favorites JSON for key '{key}'. Value: {fav_info.value}")
                pass
        
        self._cache[key] = []
        return []

    def _set_favorite_tags(self, tag_type: str, favs_list: List[str]):
        """
        Saves a list of favorite tags for a given type to the database.
        """
        key = f"favorite_{tag_type}_tags"
        if not self.session: return

        fav_info = self.session.query(GameInfoDB).filter_by(key=key).first()
        json_val = json.dumps(sorted(favs_list))

        if not fav_info:
            fav_info = GameInfoDB(key=key, value=json_val)
            self.session.add(fav_info)
        else:
            fav_info.value = json_val
        
        self._cache[key] = sorted(favs_list)
        try:
            self.session.commit()
            self.signals.favorites_changed.emit()
        except Exception as e:
            logger.error(f"Failed to set favorite tags for '{key}': {e}")
            self.session.rollback()

    def toggle_favorite_tag(self, tag_name: str, tag_type: str):
        """Adds or removes a tag from the favorites list."""
        current_favs = self.get_favorite_tags(tag_type).copy()
        if tag_name in current_favs:
            current_favs.remove(tag_name)
        else:
            current_favs.append(tag_name) 
        self._set_favorite_tags(tag_type, current_favs)

    def reset_favorite_tags(self, tag_type: str):
        """Clears all favorite tags for a given type."""
        self._set_favorite_tags(tag_type, [])