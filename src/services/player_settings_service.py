import json
import logging
from typing import List
from sqlalchemy.orm import Session

from core.game_signals import GameSignals
from database.db_models import GameInfoDB

logger = logging.getLogger(__name__)

class PlayerSettingsService:
    """
    Manages player-specific settings that are persisted in the database,
    such as favorite tags.
    """
    def __init__(self, session_factory, signals: GameSignals):
        self.session_factory = session_factory
        self.signals = signals
        self._cache = {}

    def clear_cache(self):
        self._cache.clear()

    # --- Tag Favorites System ---

    def get_favorite_tags(self, tag_type: str) -> List[str]:
        """
        Fetches the list of favorite tags for a given type. Read-only operations
        can safely use the 'with' statement for clean session management.
        """
        key = f"favorite_{tag_type}_tags"
        if key in self._cache:
            return self._cache[key]
            
        with self.session_factory() as session:
            # ... (rest of the get method is fine) ...
            fav_info = session.query(GameInfoDB).filter_by(key=key).first()
            if fav_info and fav_info.value:
                try:
                    favs = json.loads(fav_info.value)
                    self._cache[key] = favs
                    return favs
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Could not parse favorites JSON for key '{key}'. Value: {fav_info.value}")
            
            self._cache[key] = []
            return []

    def _set_favorite_tags_internal(self, session: Session, tag_type: str, favs_list: List[str]):
        """
        Internal helper. Modifies state in the session but DOES NOT COMMIT.
        The caller is responsible for the transaction.
        """
        key = f"favorite_{tag_type}_tags"
        favs_list_sorted = sorted(favs_list)
        json_val = json.dumps(favs_list_sorted)

        fav_info = session.query(GameInfoDB).filter_by(key=key).first()

        if not fav_info:
            fav_info = GameInfoDB(key=key, value=json_val)
            session.add(fav_info)
        else:
            fav_info.value = json_val
        
        # Update the cache, but don't commit or emit signals here.
        self._cache[key] = favs_list_sorted

    def toggle_favorite_tag(self, tag_name: str, tag_type: str):
        """Adds or removes a tag from the favorites list. Manages its own transaction."""
        session = self.session_factory()
        try:
            # Note: We must get current favs *before* creating the session
            # to avoid using a different session for the read.
            # A better way is to pass the session to the get method. For simplicity,
            # we'll use the cached or freshly loaded value.
            current_favs = self.get_favorite_tags(tag_type).copy()
            
            if tag_name in current_favs:
                current_favs.remove(tag_name)
            else:
                current_favs.append(tag_name) 
            
            self._set_favorite_tags_internal(session, tag_type, current_favs)
            
            session.commit()
            self.signals.favorites_changed.emit()
        except Exception as e:
            logger.error(f"Failed to toggle favorite tag '{tag_name}': {e}", exc_info=True)
            session.rollback()
        finally:
            session.close()

    def reset_favorite_tags(self, tag_type: str):
        """Clears all favorite tags for a given type. Manages its own transaction."""
        session = self.session_factory()
        try:
            self._set_favorite_tags_internal(session, tag_type, [])
            session.commit()
            self.signals.favorites_changed.emit()
        except Exception as e:
            logger.error(f"Failed to reset favorite tags for '{tag_type}': {e}", exc_info=True)
            session.rollback()
        finally:
            session.close()