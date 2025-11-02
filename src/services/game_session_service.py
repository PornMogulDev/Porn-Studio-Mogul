import logging
from typing import Optional

from data.game_state import GameState, MarketGroupState
from data.save_manager import SaveManager, LIVE_SESSION_NAME, QUICKSAVE_NAME, EXITSAVE_NAME
from core.talent_generator import TalentGenerator
from data.data_manager import DataManager
from core.game_signals import GameSignals
from database.db_models import (GameInfoDB, MarketGroupStateDB, TalentDB,
GoToListCategoryDB, EmailMessageDB)

logger = logging.getLogger(__name__)

class GameSessionService:
    """
    Manages the game session lifecycle: new, save, load, quit.
    This service is responsible for initializing the database for a new game
    and handling file-based save/load operations via the SaveManager.
    """
    def __init__(self, save_manager: SaveManager, data_manager: DataManager,
        signals: GameSignals, talent_generator: TalentGenerator):
        self.save_manager = save_manager
        self.data_manager = data_manager
        self.signals = signals
        self.talent_generator = talent_generator
        self.game_constant = self.data_manager.game_config
        self.market_data = self.data_manager.market_data
        
    def start_new_game(self) -> tuple[GameState, any, str]:
        """
        Creates a new game database, initializes it with starting data,
        and returns the essential state for the controller.
        """
        # Ensure any previous session is disconnected before starting fresh.
        self.save_manager.db_manager.disconnect()
        save_path = self.save_manager.create_new_save_db(LIVE_SESSION_NAME)
        session = self.save_manager.db_manager.get_session()
        try:

            game_state = GameState(
                week=1, 
                year=self.game_constant["starting_year"], 
                money=self.game_constant["initial_money"]
            )

            # Initialize GameInfo
            game_info_data = [
                GameInfoDB(key='week', value=str(game_state.week)),
                GameInfoDB(key='year', value=str(game_state.year)),
                GameInfoDB(key='money', value=str(game_state.money))
            ]
            session.add_all(game_info_data)

            # Initialize Market Groups
            all_group_names = [g['name'] for g in self.market_data.get('viewer_groups', [])]
            for group in self.market_data.get('viewer_groups', []):
                if name := group.get('name'):
                    market_state = MarketGroupState(name=name)
                    session.add(MarketGroupStateDB.from_dataclass(market_state))
            
            # Generate initial talent pool
            initial_talents = self.talent_generator.generate_multiple_talents(150, start_id=1)
            for talent in initial_talents:
                for name in all_group_names: talent.popularity[name] = 0.0
                session.add(TalentDB.from_dataclass(talent))

            # Create default Go-To List category
            general_category = GoToListCategoryDB(name="General", is_deletable=False)
            session.add(general_category)

            # Create welcome email
            welcome_email = EmailMessageDB(
                subject="Welcome to the Studio!", 
                body="Welcome to your new studio! Your goal is to become a successful producer.\n\nDesign scenes, cast talent, and make a profit!\n\nGood luck!",
                week=game_state.week,
                year=game_state.year,
                is_read=False
            )
            session.add(welcome_email)

            session.commit()
            return game_state, save_path
        except Exception as e:
            logger.error(f"Couldn't create a new game: {e}", exc_info=True)
            session.rollback()
            return False
        finally:
            session.close()

    def load_game(self, save_name: str) -> Optional[tuple[GameState, any, str]]:
        """
        Loads a game from a save file by copying it to the live session.
        Returns the essential game state for the controller.
        """
        try:
            # Step 1: Disconnect any previously active session to ensure a clean slate.
            self.save_manager.db_manager.disconnect()

            # Step 2: This method copies the save file AND connects the DB manager to it.
            game_state = self.save_manager.load_game(save_name)

            # Step 3: Now that a connection is established, we can safely get the session.
            save_path = self.save_manager.db_manager.db_path
            
            return game_state, save_path
        except FileNotFoundError:
            logger.error(f"Attempted to load a save file that does not exist: {save_name}")
            self.signals.notification_posted.emit(f"Error: Save file '{save_name}' not found.")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred while loading game '{save_name}': {e}", exc_info=True)
            self.signals.notification_posted.emit("A critical error occurred while loading the game.")
            return None

    def continue_game(self) -> Optional[tuple[GameState, any, str]]:
        """Loads the most recent save file."""
        latest_save = self.save_manager.load_latest_save()
        if latest_save:
            return self.load_game(latest_save)
        return None

    def save_game(self, save_name: str):
        """Saves the current game session to a named file."""
        # The service is now self-sufficient. It gets the session and path from its own manager.
        session = self.save_manager.db_manager.get_session()
        current_save_path = self.save_manager.db_manager.db_path

        if session and current_save_path:
            try:
                session.commit() # Commit any pending changes.
                self.save_manager.copy_save(current_save_path, save_name)
                self.signals.saves_changed.emit()
            except Exception as e:
                logger.error(f"Failed to save game to '{save_name}': {e}")
                session.rollback()
                self.signals.notification_posted.emit("Error: Could not save the game.")
            finally:
                session.close()

    def quick_save(self):
        self.save_game(QUICKSAVE_NAME)
        self.signals.notification_posted.emit("Game quick saved!")

    def quick_load(self) -> Optional[tuple[GameState, any, str]]:
        if self.save_manager.quick_load_exists():
            self.signals.notification_posted.emit("Game quick loaded!")
            return self.load_game(QUICKSAVE_NAME)
        else:
            self.signals.notification_posted.emit("No quick save found!")
            return None

    def delete_save(self, save_name: str) -> bool:
        if self.save_manager.delete_save(save_name): 
            self.signals.saves_changed.emit()
            return True
        return False

    def handle_exit_save(self, exit_save: bool):
        """Handles saving the game on exit if requested."""
        if exit_save and self.save_manager.db_manager.db_path:
             self.save_game(EXITSAVE_NAME)