import logging
import sqlite3

from core.ai_studio_generator import AIStudioGenerator
from core.game_signals import GameSignals
from core.talent_generator import TalentGenerator
from data.data_manager import DataManager
from data.game_state import GameState, MarketGroupState, StudioState
from data.save_manager import EXITSAVE_NAME, QUICKSAVE_NAME, SaveManager
from database.db_models import (
    AIStudioDB, GameInfoDB, GoToListCategoryDB, MarketGroupStateDB, StudioStateDB, TalentDB,
)

logger = logging.getLogger(__name__)


class GameSessionService:
    """Starts, loads and saves games using the active working database."""

    def __init__(self, save_manager: SaveManager, data_manager: DataManager,
                 signals: GameSignals, talent_generator: TalentGenerator,
                 ai_studio_generator: AIStudioGenerator):
        self.save_manager = save_manager
        self.signals = signals
        self.talent_generator = talent_generator
        self.ai_studio_generator = ai_studio_generator
        self.game_constant = data_manager.game_config
        self.market_data = data_manager.market_data

    def start_new_game(self) -> GameState | None:
        try:
            studio = StudioState(
                money=self.game_constant["initial_money"],
                location=self.game_constant["default_player_studio_location"],
            )
            state = GameState(studio=studio, absolute_week=1)
            with self.save_manager.replace_session() as candidate:
                with candidate.get_session() as session, session.begin():
                    session.add(GameInfoDB(key="absolute_week", value=str(state.absolute_week)))
                    studio_db = StudioStateDB.from_dataclass(studio)
                    studio_db.id = 1
                    session.add(studio_db)

                    group_names = [group["name"] for group in self.market_data.get("viewer_groups", [])]
                    for name in group_names:
                        if name:
                            session.add(MarketGroupStateDB.from_dataclass(MarketGroupState(name=name)))
                    for talent in self.talent_generator.generate_multiple_talents(150, start_id=1):
                        for name in group_names:
                            talent.popularity[name] = 0.0
                        session.add(TalentDB.from_dataclass(talent))

                    session.add(GoToListCategoryDB(name="General", is_deletable=False))
                    for rival in self.ai_studio_generator.generate_studios(count=4, start_id=1):
                        session.add(AIStudioDB.from_dataclass(rival))
                self.signals.session_changing.emit()
            return state
        except Exception:
            logger.exception("Could not create a new game")
            self.signals.notification_posted.emit("Error: Could not start a new game.")
            return None

    def load_game(self, save_name: str) -> GameState | None:
        try:
            with self.save_manager.replace_session(save_name) as candidate:
                with candidate.get_session() as session:
                    week = session.get(GameInfoDB, "absolute_week")
                    studio = session.get(StudioStateDB, 1)
                    if week is None or studio is None or int(week.value) < 1:
                        raise ValueError("Save is missing valid game state.")
                    state = GameState(absolute_week=int(week.value), studio=studio.to_dataclass(StudioState))
                self.signals.session_changing.emit()
            return state
        except FileNotFoundError:
            logger.warning("Save file %r was not found", save_name)
            self.signals.notification_posted.emit(f"Error: Save file '{save_name}' not found.")
        except Exception:
            logger.exception("Could not load save %r", save_name)
            self.signals.notification_posted.emit("Error: Could not load the selected save.")
        return None

    def continue_game(self) -> GameState | None:
        latest_save = self.save_manager.load_latest_save()
        if latest_save:
            return self.load_game(latest_save)
        return None

    def save_game(self, save_name: str) -> bool:
        try:
            self.save_manager.save_game(save_name)
        except (OSError, sqlite3.Error, ValueError):
            logger.exception("Could not write save %r", save_name)
            self.signals.notification_posted.emit("Error: Could not save the game.")
            return False
        self.signals.saves_changed.emit()
        return True

    def auto_save(self):
        try:
            self.save_manager.auto_save()
        except (OSError, sqlite3.Error):
            logger.exception("Could not write autosave")
            self.signals.notification_posted.emit("Error: Could not create an autosave.")
            return
        self.signals.saves_changed.emit()

    def quick_save(self):
        if self.save_game(QUICKSAVE_NAME):
            self.signals.notification_posted.emit("Game quick saved!")

    def quick_load(self) -> GameState | None:
        if self.save_manager.quick_load_exists():
            return self.load_game(QUICKSAVE_NAME)
        self.signals.notification_posted.emit("No quick save found!")
        return None

    def delete_save(self, save_name: str) -> bool:
        if self.save_manager.delete_save(save_name):
            self.signals.saves_changed.emit()
            return True
        return False

    def handle_exit_save(self, exit_save: bool) -> bool:
        if exit_save and self.save_manager.get_current_session_path():
            return self.save_game(EXITSAVE_NAME)
        return True

    def has_saves(self) -> bool:
        return self.save_manager.has_saves()
