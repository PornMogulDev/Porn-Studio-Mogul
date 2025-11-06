import logging
from typing import List, Dict, Optional, Tuple, Set
from PyQt6.QtCore import QObject
from sqlalchemy import func

from core.service_container import ServiceContainer
from core.game_signals import GameSignals
from core.interfaces import IGameController
from data.game_state import *
from data.save_manager import SaveManager
from core.talent_generator import TalentGenerator
from data.data_manager import DataManager
from data.settings_manager import SettingsManager
from ui.theme_manager import Theme, ThemeManager
from database.db_models import *

from services.query.tag_query_service import TagQueryService
from services.query.game_query_service import GameQueryService
from services.query.talent_query_service import TalentQueryService
from services.calculation.talent_demand_calculator import TalentDemandCalculator
from services.calculation.bloc_cost_calculator import BlocCostCalculator
from services.command.talent_command_service import TalentCommandService
from services.command.scene_command_service import SceneCommandService
from services.command.scene_event_command_service import SceneEventCommandService
from services.market_service import MarketService
from services.time_service import TimeService
from services.go_to_list_service import GoToListService
from services.game_session_service import GameSessionService
from services.player_settings_service import PlayerSettingsService
from services.email_service import EmailService
from services.models.results import EventAction

logger = logging.getLogger(__name__)

class GameController(QObject):
    def __init__(self, settings_manager: SettingsManager, data_manager: DataManager, theme_manager: ThemeManager,
                 save_manager: SaveManager, signals: GameSignals, service_container: ServiceContainer):
        super().__init__()
        self.settings_manager = settings_manager
        self.data_manager = data_manager
        self.theme_manager = theme_manager
        self.save_manager = save_manager
        self.signals = signals
        self.service_container = service_container
        self.game_state = GameState()
        
        self.current_save_path = None 
        self._graceful_shutdown_in_progress = False  # Track if shutdown is through menu 
        
        self.game_constant = self.data_manager.game_config
        self.market_data = self.data_manager.market_data
        self.affinity_data = self.data_manager.affinity_data
        self.tag_definitions = self.data_manager.tag_definitions
        self.generator_data = self.data_manager.generator_data
        self.talent_archetypes = self.data_manager.talent_archetypes
        self.help_topics = self.data_manager.help_topics
        
        self.talent_generator = TalentGenerator(self.game_constant, self.generator_data, self.affinity_data, self.tag_definitions, self.talent_archetypes)
        
        self.game_session_service = GameSessionService(self.save_manager, self.data_manager, self.signals, self.talent_generator)

       # --- Service Properties (will be populated by ServiceContainer) ---
        self.query_service: Optional[GameQueryService] = None
        self.tag_query_service: Optional['TagQueryService'] = None # Forward ref if needed
        self.talent_command_service: Optional[TalentCommandService] = None
        self.scene_command_service: Optional[SceneCommandService] = None
        self.market_service: Optional[MarketService] = None
        self.talent_query_service: Optional[TalentQueryService] = None
        self.talent_demand_calculator: Optional[TalentDemandCalculator] = None
        self.bloc_cost_calculator: Optional[BlocCostCalculator] = None
        self.time_service: Optional[TimeService] = None
        self.go_to_list_service: Optional[GoToListService] = None
        self.scene_event_command_service: Optional[SceneEventCommandService] = None
        self.player_settings_service: Optional[PlayerSettingsService] = None
        self.email_service: Optional[EmailService] = None
        
        self._cached_thematic_tags_data = None
        self._cached_physical_tags_data = None
        self._cached_action_tags_data = None

        self._available_ethnicities = None
        self.game_over = False

    def get_current_theme(self) -> Theme:
        """Convenience method to get the current theme object."""
        theme_name = self.settings_manager.get_setting("theme", "dark")
        return self.theme_manager.get_theme(theme_name)

    def get_available_ethnicities(self) -> list[str]:
        if self._available_ethnicities is None:
            self._available_ethnicities = ["Any"] + sorted([e['name'] for e in self.generator_data.get('ethnicities', [])])
        return self._available_ethnicities

    def get_available_boob_cups(self) -> list[str]:
        return [b['name'] for b in self.generator_data.get('boob_cups', [])]

    # --- UI Data Access Methods ---
    def get_talent_by_id(self, talent_id: int) -> Optional[Talent]:
        if not self.query_service: return None
        return self.query_service.get_talent_by_id(talent_id)
    
    def get_filtered_talents(self, filters: dict) -> List[Talent]:
        if not self.query_service: return []
        return self.query_service.get_filtered_talents(filters)

    def get_blocs_for_schedule_view(self, year: int) -> List[ShootingBloc]:
        if not self.query_service: return []
        return self.query_service.get_blocs_for_schedule_view(year)

    def get_bloc_by_id(self, bloc_id: int) -> Optional[ShootingBloc]:
        if not self.query_service: return None
        return self.query_service.get_bloc_by_id(bloc_id)

    def get_scene_for_planner(self, scene_id: int) -> Optional[Scene]:
        if not self.query_service: return None
        return self.query_service.get_scene_for_planner(scene_id)
        
    def get_shot_scenes(self) -> List[Scene]:
        if not self.query_service: return []
        return self.query_service.get_shot_scenes()
        
    def get_all_market_states(self) -> Dict[str, MarketGroupState]:
        if not self.query_service: return {}
        return self.query_service.get_all_market_states()
        
    def get_scene_history_for_talent(self, talent_id: int) -> List[Scene]:
        if not self.query_service: return []
        return self.query_service.get_scene_history_for_talent(talent_id)

    def get_castable_scenes(self) -> List[Dict]:
        """Gets a simplified list of scenes in 'casting' for UI filters."""
        if not self.query_service: return []
        return self.query_service.get_castable_scenes_for_ui()

    def get_uncast_roles_for_scene(self, scene_id: int) -> List[Dict]:
        """Gets a list of uncast roles for a specific scene for UI filters."""
        if not self.query_service: return []
        return self.query_service.get_uncast_roles_for_scene_ui(scene_id)

    # --- Go-To List Data Access (Proxy Methods) ---
    def get_go_to_list_talents(self) -> List[Talent]:
        if not self.query_service: return []
        return self.query_service.get_all_talents_in_go_to_lists()

    def get_go_to_list_categories(self) -> List[Dict]:
        if not self.query_service: return []
        return self.query_service.get_all_categories()

    def get_talents_in_go_to_category(self, category_id: int) -> List[Talent]:
        if not self.query_service: return []
        return self.query_service.get_talents_in_category(category_id)

    def get_talent_go_to_categories(self, talent_id: int) -> List[Dict]:
        if not self.query_service: return []
        return self.query_service.get_talent_categories(talent_id)

    def get_all_emails(self) -> List[EmailMessage]:
        if not self.query_service: return []
        return self.query_service.get_all_emails()

    # --- Game Logic ---
    def advance_week(self):
        if self.game_over: return

        # Pre-flight check
        incomplete_scenes = self.query_service.get_incomplete_scenes_for_week(
            self.game_state.week, self.game_state.year
        )
        if incomplete_scenes:
            self.signals.incomplete_scene_check_requested.emit(incomplete_scenes)
            return

        # Delegate everything to TimeService
        result = self.time_service.advance_week()

        # Update local state
        self.game_state.week = result.new_week
        self.game_state.year = result.new_year
        self.game_state.money = result.new_money

        # Autosave with a fresh session (SaveManager handles this)
        self.save_manager.auto_save()

        # Handle pauses
        if result.was_paused:
            if result.scenes_shot > 0: self.signals.scenes_changed.emit()
            return

        # Check game over
        if self.game_state.money <= self.game_constant.get('game_over_threshold', -5000):
            self.signals.game_over_triggered.emit("bankruptcy")
            return

        # Emit signals
        self.signals.time_changed.emit(result.new_week, result.new_year)
        self.signals.money_changed.emit(self.game_state.money)
        if result.scenes_shot > 0 or result.scenes_edited > 0: self.signals.scenes_changed.emit()
        if result.market_changed: self.signals.market_changed.emit()
        if result.talent_pool_changed: self.signals.talent_pool_changed.emit()

    def start_editing_scene(self, scene_id: int, editing_tier_id: str):
        """
        Starts the editing process for a shot scene. The controller is responsible for
        committing the transaction and emitting signals after the service runs.
        """
        success, cost = self.scene_command_service.start_editing_scene(scene_id, editing_tier_id)

    def release_scene(self, scene_id: int):
        # Capture the returned dictionary of discoveries
        result = self.scene_command_service.release_scene(scene_id)
        if not result:
            return

        self.signals.notification_posted.emit(f"'{result['title']}' released! Revenue: +${result['revenue']:,}")
        self.signals.scenes_changed.emit()
        self.signals.money_changed.emit(result['new_money'])
        self.signals.market_changed.emit()

        if result['market_changed']:
            # The emails_changed signal is now emitted by the EmailService itself,
            # so we don't need to call it here.
            for group_name in result['discoveries']:
                self.signals.notification_posted.emit(f"New market insights gained for '{group_name}'!")
            # We are emitting this anyway at the moment.
            # When we move to a "gradual release" we will update this.
            # self.signals.market_changed.emit()
            
    def create_shooting_bloc(self, week: int, year: int, num_scenes: int, settings: Dict[str, str], name: str, policies: List[str]) -> bool:
        """
        Calculates the cost authoritatively and creates a shooting bloc.
        This version does NOT accept a 'cost' parameter from the UI.
        """
        return self.scene_command_service.create_shooting_bloc(week, year, num_scenes, settings, name, policies)
    
    def calculate_shooting_bloc_cost(self, num_scenes: int, settings: Dict, policies: List[str]) -> int:
        """Proxy method for the UI to get a cost estimate from the authoritative service."""
        if not self.bloc_cost_calculator: return 0
        return self.bloc_cost_calculator.calculate_shooting_bloc_cost(num_scenes, settings, policies)

    def create_blank_scene(self, week: Optional[int] = None, year: Optional[int] = None) -> int:
        use_week = week if week is not None else self.game_state.week
        use_year = year if year is not None else self.game_state.year
        return self.scene_command_service.create_blank_scene(use_week, use_year)
    
    def delete_scene(self, scene_id: int, penalty_percentage: float = 0.0): 
        self.scene_command_service.delete_scene(scene_id, penalty_percentage)

    def update_scene_full(self, scene_data: Scene) -> Dict:
        """Receives a full Scene dataclass from the presenter and updates the database."""
        return self.scene_command_service.update_scene_full(scene_data)

    def calculate_talent_demand(self, talent_id: int, scene_id: int, vp_id: int) -> int:
        return self.talent_demand_calculator.calculate_talent_demand(talent_id, scene_id, vp_id)

    def cast_talent_for_virtual_performer(self, talent_id: int, scene_id: int, virtual_performer_id: int, cost: int):
        self.scene_command_service.cast_talent_for_role(talent_id, scene_id, virtual_performer_id, cost)

    def cast_talent_for_multiple_roles(self, talent_id: int, roles: List[Dict]):
        """Casts a single talent into multiple roles across different scenes."""

        # Server-side validation as a safeguard against client-side errors or other entry points
        scene_ids = [role['scene_id'] for role in roles]
        if len(scene_ids) != len(set(scene_ids)):
            self.signals.notification_posted.emit("Casting failed: Cannot assign a talent to multiple roles in the same scene.")
            return
        self.scene_command_service.cast_talent_for_multiple_roles(talent_id, roles)

    def get_thematic_tags_for_planner(self) -> Tuple[List[Dict], Set[str], Set[str]]:
        return self.tag_query_service.get_tags_for_planner('Thematic')

    def get_physical_tags_for_planner(self) -> Tuple[List[Dict], Set[str], Set[str]]:
        return self.tag_query_service.get_tags_for_planner('Physical')

    def get_action_tags_for_planner(self) -> Tuple[List[Dict], Set[str], Set[str]]:
        return self.tag_query_service.get_tags_for_planner('Action')

    def get_resolved_group_data(self, group_name: str) -> Dict: return self.market_service.get_resolved_group_data(group_name)

    def resolve_interactive_event(self, event_id: str, scene_id: int, talent_id: int, choice_id: str) -> None:
        """Orchestrates event resolution and shoot continuation."""
        if not self.scene_event_command_service or not self.scene_command_service:
            return
        
        # 1. Delegate resolution to the command service. It returns a result DTO.
        result = self.scene_event_command_service.resolve_interactive_event(
            event_id, scene_id, talent_id, choice_id
        )

        # 2. Post a notification if the result included one.
        if result.notification:
            self.signals.notification_posted.emit(result.notification)

        # 3. Orchestrate the next action based on the result DTO.
        if result.next_action == EventAction.CANCEL_SCENE:
            # The controller, not the event service, calls the scene command service.
            self.scene_command_service.delete_scene(scene_id, result.cancellation_penalty)
            self.advance_week() # Continue the week after cancellation.
        
        elif result.next_action == EventAction.CHAIN_EVENT:
            # The controller, not the event service, emits the signal for the new event.
            payload = result.chained_event_payload
            self.signals.interactive_event_triggered.emit(
                payload['event_data'], payload['scene_id'], payload['talent_id']
            )

        elif result.next_action == EventAction.CONTINUE_SHOOT:
            self.scene_command_service.continue_shoot_scene_after_event(scene_id, result.shoot_modifiers)
            self.advance_week() # Continue the week after a successful shoot.

    # --- Game Session Management (Delegated to GameSessionService) ---

    def new_game_started(self):
        """Initializes a new game session."""
        result = self.game_session_service.start_new_game()
        if result:
            self.game_state, self.current_save_path = result
            self.service_container.initialize_and_populate_services(self, self.game_state)
            
            self.signals.money_changed.emit(self.game_state.money)
            self.signals.time_changed.emit(self.game_state.week, self.game_state.year)
            self.signals.talent_pool_changed.emit()
            self.signals.new_game_started.emit()
            self.signals.show_main_window_requested.emit()
        
    def load_game(self, save_name: str):
        """Loads a game session from a file."""
        result = self.game_session_service.load_game(save_name)
        if result:
            self.game_state, self.current_save_path = result
            self.service_container.initialize_and_populate_services(self, self.game_state)
            
            self.signals.money_changed.emit(self.game_state.money)
            self.signals.time_changed.emit(self.game_state.week, self.game_state.year)
            self.signals.scenes_changed.emit()
            self.signals.talent_pool_changed.emit()
            self.signals.emails_changed.emit()
            self.signals.show_main_window_requested.emit()

    def save_game(self, save_name: str):
        self.game_session_service.save_game(save_name)

    def delete_save_file(self, save_name: str) -> bool:
        return self.game_session_service.delete_save(save_name)

    def continue_game(self):
        result = self.game_session_service.continue_game()
        if result:
            self.game_state, self.current_save_path = result
            self.service_container.initialize_and_populate_services(self, self.game_state)
            
            self.signals.money_changed.emit(self.game_state.money)
            self.signals.time_changed.emit(self.game_state.week, self.game_state.year)
            self.signals.scenes_changed.emit()
            self.signals.talent_pool_changed.emit()
            self.signals.emails_changed.emit()
            self.signals.show_main_window_requested.emit()

    def quick_save(self):
        self.game_session_service.quick_save()

    def quick_load(self):
        result = self.game_session_service.quick_load()
        if result:
            self.game_state, self.current_save_path = result
            self.service_container.initialize_and_populate_services(self, self.game_state)
            self.signals.money_changed.emit(self.game_state.money)
            self.signals.time_changed.emit(self.game_state.week, self.game_state.year)
            self.signals.scenes_changed.emit()
            self.signals.talent_pool_changed.emit()
            self.signals.emails_changed.emit()
            self.signals.show_main_window_requested.emit()

    def return_to_main_menu(self, exit_save: bool):
        self._graceful_shutdown_in_progress = True
        self.game_session_service.handle_exit_save(exit_save and not self.game_over)
        self.service_container.cleanup_services(self)
        self.current_save_path = None
        self.game_over = False
        self._graceful_shutdown_in_progress = False # Reset for next session
        self.signals.show_start_screen_requested.emit()

    def quit_game(self, exit_save: bool = False):
        self._graceful_shutdown_in_progress = True
        self.game_session_service.handle_exit_save(exit_save and not self.game_over)
        self.service_container.cleanup_services(self)
        self._graceful_shutdown_in_progress = False # Reset
        self.signals.quit_game_requested.emit()
    
    def handle_application_shutdown(self):
        if self.current_save_path and not self._graceful_shutdown_in_progress:
            self.service_container.cleanup_services(self)

    def handle_game_over(self):
        self.game_over = True
        self.service_container.cleanup_services(self)
        self.current_save_path = None
        self.signals.game_over_triggered.emit("Your studio has gone bankrupt.")

    def check_for_saves(self) -> bool:
        """Checks if any save files exist to enable 'Continue' button."""
        return self.game_session_service.has_saves()
        
    # --- Other Methods ---

    def get_unread_email_count(self) -> int:
        if not self.query_service: return 0
        return self.query_service.get_unread_email_count()

    def mark_email_as_read(self, email_id: int):
        if not self.email_service: return
        self.email_service.mark_email_as_read(email_id)

    def delete_emails(self, email_ids: list[int]):
        if not self.email_service: return
        self.email_service.delete_emails(email_ids)

    # --- Go-To List Actions (Proxy Methods) ---

    def remove_talents_from_go_to_list(self, talent_ids: list[int]):
        if not self.go_to_list_service: return
        self.go_to_list_service.remove_talents_from_all_categories(talent_ids)

    def create_go_to_list_category(self, name: str):
        if not self.go_to_list_service: return
        self.go_to_list_service.create_category(name)

    def rename_go_to_list_category(self, category_id: int, new_name: str):
        if not self.go_to_list_service: return
        self.go_to_list_service.rename_category(category_id, new_name)

    def delete_go_to_list_category(self, category_id: int):
        if not self.go_to_list_service: return
        self.go_to_list_service.delete_category(category_id)

    def add_talent_to_go_to_category(self, talent_id: int, category_id: int):
        if not self.go_to_list_service: return
        self.go_to_list_service.add_talents_to_category([talent_id], category_id)

    def add_talents_to_go_to_category(self, talent_ids: list[int], category_id: int):
        if not self.go_to_list_service: return
        self.go_to_list_service.add_talents_to_category(talent_ids, category_id)

    def remove_talent_from_go_to_category(self, talent_id: int, category_id: int):
        if not self.go_to_list_service: return
        self.go_to_list_service.remove_talents_from_category([talent_id], category_id)

    def remove_talents_from_go_to_category(self, talent_ids: list[int], category_id: int):
        if not self.go_to_list_service: return
        self.go_to_list_service.remove_talents_from_category(talent_ids, category_id)

    # --- Tag Favorites System (Delegated to PlayerSettingsService) ---
    def get_favorite_tags(self, tag_type: str) -> List[str]:
        if not self.player_settings_service: return []
        return self.player_settings_service.get_favorite_tags(tag_type)

    def toggle_favorite_tag(self, tag_name: str, tag_type: str):
        if not self.player_settings_service: return
        self.player_settings_service.toggle_favorite_tag(tag_name, tag_type)

    def reset_favorite_tags(self, tag_type: str):
        if not self.player_settings_service: return
        self.player_settings_service.reset_favorite_tags(tag_type)