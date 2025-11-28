import logging
from sqlalchemy.orm import Session
from core.game_signals import GameSignals
from database.db_models import StudioStateDB
from data.game_state import GameState

logger = logging.getLogger(__name__)

class StudioCommandService:
    def __init__(self, session_factory, signals: GameSignals, game_state: GameState):
        self.session_factory = session_factory
        self.signals = signals
        self.game_state = game_state

    def toggle_policy(self, policy_id: str, is_active: bool) -> bool:
        """
        Toggles a studio policy in the DB and updates local state.
        Follows 'Public Command Method' pattern.
        """
        session = self.session_factory()
        try:
            # 1. Fetch the Studio State (Singleton ID 1)
            studio_db = session.query(StudioStateDB).get(1)
            if not studio_db:
                logger.error("Studio state not found in database.")
                return False

            # 2. Modify the list (Copy to set for easy manipulation)
            current_policies = set(studio_db.studio_policies)
            
            if is_active:
                current_policies.add(policy_id)
                # (Optional) Handle immediate implementation costs here if logic dictates
            else:
                current_policies.discard(policy_id)

            # 3. Apply changes to DB entity
            # Re-assigning the list ensures SQLAlchemy detects the change in the JSON column
            studio_db.studio_policies = list(current_policies)
            
            session.commit()

            # 4. Update in-memory GameState to keep UI in sync without reload
            self.game_state.studio.studio_policies = list(current_policies)

            # 5. Emit Signal
            # Assuming you might add a 'policies_changed' signal, or strictly use generic ones
            # self.signals.studio_state_changed.emit() 
            logger.info(f"Policy '{policy_id}' toggled to {is_active}.")
            
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to toggle policy {policy_id}: {e}", exc_info=True)
            return False
        finally:
            session.close()