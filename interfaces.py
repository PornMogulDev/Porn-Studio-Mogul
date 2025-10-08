from typing import Protocol, Optional, List, Dict, Tuple, Set
from PyQt6.QtCore import QObject, pyqtSignal

# --- Import necessary types for the interface definition ---
from game_state import Scene, Talent, ShootingBloc
from services.talent_service import TalentService
from data_manager import DataManager
from settings_manager import SettingsManager

# --- Moved from game_controller.py to break circular dependency ---
class GameSignals(QObject):
    show_start_screen_requested = pyqtSignal()
    show_main_window_requested = pyqtSignal()
    money_changed = pyqtSignal(int)
    time_changed = pyqtSignal(int, int)
    roster_changed = pyqtSignal()
    scenes_changed = pyqtSignal()
    talent_pool_changed = pyqtSignal()
    talent_generated = pyqtSignal(list)
    notification_posted = pyqtSignal(str)
    interactive_event_triggered = pyqtSignal(dict, int, int)
    new_game_started = pyqtSignal()
    saves_changed = pyqtSignal()
    go_to_list_changed = pyqtSignal()
    emails_changed = pyqtSignal()
    game_over_triggered = pyqtSignal(str)
    quit_game_requested = pyqtSignal()
    market_changed = pyqtSignal()
    favorites_changed = pyqtSignal()
    incomplete_scene_check_requested = pyqtSignal(list)

# This is our "contract". It defines what a presenter or service
# needs to be able to do with a game controller.
class IGameController(Protocol):
    """
    Defines the interface for the GameController that UI components
    and presenters can rely on.
    """

    # --- Properties presenters need ---
    @property
    def talent_service(self) -> TalentService: ...

    @property
    def tag_definitions(self) -> Dict: ...

    @property
    def market_data(self) -> Dict: ...
    
    @property
    def signals(self) -> GameSignals: ...
    
    @property
    def settings_manager(self) -> SettingsManager: ...
    
    @property
    def data_manager(self) -> DataManager: ...

    # --- Methods for ScenePlannerPresenter ---
    def get_scene_for_planner(self, scene_id: int) -> Optional[Scene]: ...
    def update_scene_full(self, scene_data: Scene): ...
    def get_bloc_by_id(self, bloc_id: int) -> Optional[ShootingBloc]: ...
    def get_style_tags_for_planner(self) -> Tuple[List[Dict], Set[str], Set[str]]: ...
    def get_action_tags_for_planner(self) -> Tuple[List[Dict], Set[str], Set[str]]: ...
    def get_favorite_tags(self, tag_type: str) -> List[str]: ...
    def toggle_favorite_tag(self, tag_name: str, tag_type: str): ...
    def delete_scene(self, scene_id: int, penalty_percentage: float): ...

    # --- Methods for HireTalentPresenter ---
    def get_castable_scenes(self) -> List[Dict]: ...
    def get_uncast_roles_for_scene(self, scene_id: int) -> List[Dict]: ...
    def get_filtered_talents(self, all_filters: dict) -> List[Talent]: ...
    def cast_talent_for_multiple_roles(self, talent_id: int, roles: list): ...
    def add_talent_to_go_to_list(self, talent_id: int): ...
    def get_available_ethnicities(self) -> list[str]: ...
    def get_available_boob_cups(self) -> list[str]: ...