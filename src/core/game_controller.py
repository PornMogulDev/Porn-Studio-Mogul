import logging
from typing import List, Dict, Optional, Tuple, Set
from PyQt6.QtCore import QObject
from sqlalchemy import func

from core.interfaces import IGameController, GameSignals
from data.game_state import *
from data.save_manager import SaveManager, EXITSAVE_NAME
from core.talent_generator import TalentGenerator
from data.data_manager import DataManager
from data.settings_manager import SettingsManager
from ui.theme_manager import Theme, ThemeManager
from database.db_models import *

from services.service_config import HiringConfig
from services.market_service import MarketService
from services.talent_service import TalentService
from services.hire_talent_service import HireTalentService
from services.role_performance_service import RolePerformanceService
from services.scene_event_service import SceneEventService
from services.scene_service import SceneService
from services.time_service import TimeService
from services.go_to_list_service import GoToListService
from services.game_session_service import GameSessionService
from services.player_settings_service import PlayerSettingsService
from services.email_service import EmailService

logger = logging.getLogger(__name__)

class GameController(QObject):
    def __init__(self, settings_manager: SettingsManager, data_manager: DataManager, theme_manager: ThemeManager):
        super().__init__()
        self.settings_manager = settings_manager
        self.data_manager = data_manager
        self.theme_manager = theme_manager
        self.game_state = GameState()
        self.save_manager = SaveManager()
        self.signals = GameSignals()
        
        self.db_session = None
        self.current_save_path = None 
        
        self.game_constant = self.data_manager.game_config
        self.tag_definitions = self.data_manager.tag_definitions
        self.market_data = self.data_manager.market_data
        self.affinity_data = self.data_manager.affinity_data
        self.generator_data = self.data_manager.generator_data
        self.talent_archetypes = self.data_manager.talent_archetypes
        self.help_topics = self.data_manager.help_topics
        
        self.talent_generator = TalentGenerator(self.game_constant, self.generator_data, self.affinity_data, self.tag_definitions, self.talent_archetypes)
        
        self.game_session_service = GameSessionService(self.save_manager, self.data_manager, self.signals, self.talent_generator)

        self.hiring_config = None
        self.market_service = None
        self.talent_service = None
        self.hire_talent_service = None
        self.role_performance_service = None
        self.scene_service = None
        self.time_service = None
        self.go_to_list_service = None
        self.scene_event_service = None
        self.player_settings_service = None
        self.email_service = None
        
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
    def get_filtered_talents(self, filters: dict) -> List[Talent]:
        if not self.talent_service: return []
        return self.talent_service.get_filtered_talents(filters)

    def get_blocs_for_schedule_view(self, year: int) -> List[ShootingBloc]:
        if not self.scene_service: return []
        return self.scene_service.get_blocs_for_schedule_view(year)

    def get_bloc_by_id(self, bloc_id: int) -> Optional[ShootingBloc]:
        if not self.scene_service: return None
        return self.scene_service.get_bloc_by_id(bloc_id)

    def get_scene_for_planner(self, scene_id: int) -> Optional[Scene]:
        if not self.scene_service: return None
        return self.scene_service.get_scene_for_planner(scene_id)
        
    def get_shot_scenes(self) -> List[Scene]:
        if not self.scene_service: return []
        return self.scene_service.get_shot_scenes()
        
    def get_all_market_states(self) -> Dict[str, MarketGroupState]:
        if not self.market_service: return {}
        return self.market_service.get_all_market_states()
        
    def get_scene_history_for_talent(self, talent_id: int) -> List[Scene]:
        if not self.scene_service: return []
        return self.scene_service.get_scene_history_for_talent(talent_id)

    def get_castable_scenes(self) -> List[Dict]:
        """Gets a simplified list of scenes in 'casting' for UI filters."""
        if not self.scene_service: return []
        return self.scene_service.get_castable_scenes_for_ui()

    def get_uncast_roles_for_scene(self, scene_id: int) -> List[Dict]:
        """Gets a list of uncast roles for a specific scene for UI filters."""
        if not self.scene_service: return []
        return self.scene_service.get_uncast_roles_for_scene_ui(scene_id)

    # --- Go-To List Data Access (Proxy Methods) ---
    def get_go_to_list_talents(self) -> List[Talent]:
        """Gets all unique talents present in any Go-To List category."""
        if not self.db_session: return []
        
        talents_db = self.db_session.query(TalentDB)\
            .join(GoToListAssignmentDB)\
            .distinct()\
            .order_by(TalentDB.alias).all()
        return [t.to_dataclass(Talent) for t in talents_db]

    def get_go_to_list_categories(self) -> List[Dict]:
        if not self.go_to_list_service: return []
        return self.go_to_list_service.get_all_categories()

    def get_talents_in_go_to_category(self, category_id: int) -> List[Talent]:
        if not self.go_to_list_service: return []
        return self.go_to_list_service.get_talents_in_category(category_id)

    def get_talent_go_to_categories(self, talent_id: int) -> List[Dict]:
        if not self.go_to_list_service: return []
        return self.go_to_list_service.get_talent_categories(talent_id)

    def get_all_emails(self) -> List[EmailMessage]:
        if not self.email_service: return []
        return self.email_service.get_all_emails()

    # --- Game Logic ---
    def advance_week(self):
        if self.game_over: return

        # Pre-flight check for incomplete scenes scheduled for this week
        incomplete_scenes = self.scene_service.get_incomplete_scenes_for_week(
            self.game_state.week, self.game_state.year
        )
        if incomplete_scenes:
            self.signals.incomplete_scene_check_requested.emit(incomplete_scenes)
            return  # Stop here, wait for UI to handle and possibly recall this method

        # --- 1. PROCESS WEEK ADVANCEMENT ---
        # All game logic for the week happens here, before saving.
        changes = self.time_service.process_week_advancement()
        
        # Update GameState money from DB before committing and saving
        money_info = self.db_session.query(GameInfoDB).filter_by(key='money').one()
        self.game_state.money = int(float(money_info.value))

        # Commit all changes from the week advancement to the database
        self.db_session.commit()

        # --- 2. AUTOSAVE AFTER ALL CHANGES ARE COMMITTED ---
        # The autosave will now contain the state of the *new* week.
        self.save_manager.auto_save(self.db_session)
        
        # After auto_save, the session is rebound. We need to get the new session
        # and re-initialize services with it for the next player action.
        self.db_session = self.save_manager.db_manager.get_session()
        self._reinitialize_services()

        # --- 3. EMIT SIGNALS AND HANDLE PAUSES/GAME OVER ---
        if changes.get("paused"):  # If the week was paused by an event..._
            if changes.get("scenes_shot") or changes.get("scenes_edited"): self.signals.scenes_changed.emit()
            return

        # Emit signals for all changes that occurred during the week
        if changes.get("scenes_shot") or changes.get("scenes_edited"): self.signals.scenes_changed.emit()
        if changes.get("market"): self.signals.market_changed.emit()
        if changes.get("talent_pool"): self.signals.talent_pool_changed.emit()

        # Check for game over condition
        if self.game_state.money <= self.game_constant.get('game_over_threshold', -5000):
            self.signals.game_over_triggered.emit("bankruptcy")
            return

        # Finally, signal that the time and money have officially changed for the new week
        self.signals.time_changed.emit(self.game_state.week, self.game_state.year)
        self.signals.money_changed.emit(self.game_state.money)

    def start_editing_scene(self, scene_id: int, editing_tier_id: str):
        """
        Starts the editing process for a shot scene. The controller is responsible for
        committing the transaction and emitting signals after the service runs.
        """
        success, cost = self.scene_service.start_editing_scene(scene_id, editing_tier_id)

    def release_scene(self, scene_id: int):
        # Capture the returned dictionary of discoveries
        result = self.scene_service.release_scene(scene_id)
        if not result:
            return

        self.signals.notification_posted.emit(f"'{result['title']}' released! Revenue: +${result['revenue']:,}")
        self.signals.scenes_changed.emit()
        self.signals.money_changed.emit(result['new_money'])

        if result['market_changed']:
            # The emails_changed signal is now emitted by the EmailService itself,
            # so we don't need to call it here.
            for group_name in result['discoveries']:
                self.signals.notification_posted.emit(f"New market insights gained for '{group_name}'!")
            self.signals.market_changed.emit()
            
    def create_shooting_bloc(self, week: int, year: int, num_scenes: int, settings: Dict[str, str], name: str, policies: List[str]) -> bool:
        """
        Calculates the cost authoritatively and creates a shooting bloc.
        This version does NOT accept a 'cost' parameter from the UI.
        """
        if not self.scene_service: return False

        # --- Authoritative server-side cost calculation ---
        total_cost_per_scene = 0

        # Special handling for Camera cost
        cam_equip_tier_name = settings.get("Camera Equipment")
        cam_setup_tier_name = settings.get("Camera Setup")
        
        equip_cost = 0
        if cam_equip_tier_name:
            tiers = self.data_manager.production_settings_data.get("Camera Equipment", [])
            tier_info = next((t for t in tiers if t['tier_name'] == cam_equip_tier_name), None)
            if tier_info:
                equip_cost = tier_info.get('cost_per_scene', 0)

        setup_multiplier = 1.0
        if cam_setup_tier_name:
            tiers = self.data_manager.production_settings_data.get("Camera Setup", [])
            tier_info = next((t for t in tiers if t['tier_name'] == cam_setup_tier_name), None)
            if tier_info:
                setup_multiplier = tier_info.get('cost_multiplier', 1.0)
        
        total_cost_per_scene += equip_cost * setup_multiplier

        # Add costs from all other standard categories
        for category, tier_name in settings.items():
            if category in ["Camera Equipment", "Camera Setup"]:
                continue
            tiers = self.data_manager.production_settings_data.get(category, [])
            tier_info = next((t for t in tiers if t['tier_name'] == tier_name), None)
            if tier_info:
                total_cost_per_scene += tier_info.get('cost_per_scene', 0)
        
        settings_cost = total_cost_per_scene * num_scenes

        # Cost from policies (per bloc)
        policies_cost = 0
        for policy_id in policies:
            if policy_data := self.data_manager.on_set_policies_data.get(policy_id):
                policies_cost += policy_data.get('cost_per_bloc', 0)
        
        final_cost = int(settings_cost + policies_cost) # Ensure final cost is an integer
        
        if self.game_state.money < final_cost:
            self.signals.notification_posted.emit(f"Not enough money. Cost: ${final_cost:,}, Have: ${self.game_state.money:,}")
            return False
        
        final_name = name.strip() if name.strip() else f"{year} W{week} Shoot"
        
        return self.scene_service.create_shooting_bloc(week, year, num_scenes, settings, final_cost, final_name, policies)
    
    def create_blank_scene(self, week: Optional[int] = None, year: Optional[int] = None) -> int:
        use_week = week if week is not None else self.game_state.week
        use_year = year if year is not None else self.game_state.year
        return self.scene_service.create_blank_scene(use_week, use_year)
    
    def delete_scene(self, scene_id: int, silent: bool = False, penalty_percentage: float = 0.0): 
        self.scene_service.delete_scene(scene_id, penalty_percentage, silent)

    def update_scene_full(self, scene_data: Scene) -> Dict:
        """Receives a full Scene dataclass from the presenter and updates the database."""
        return self.scene_service.update_scene_full(scene_data)

    def calculate_talent_demand(self, talent_id: int, scene_id: int, vp_id: int) -> int:
        return self.hire_talent_service.calculate_talent_demand(talent_id, scene_id, vp_id)

    def cast_talent_for_virtual_performer(self, talent_id: int, scene_id: int, virtual_performer_id: int, cost: int):
        self.scene_service.cast_talent_for_role(talent_id, scene_id, virtual_performer_id, cost)

    def cast_talent_for_multiple_roles(self, talent_id: int, roles: List[Dict]):
        """Casts a single talent into multiple roles across different scenes."""

        # Server-side validation as a safeguard against client-side errors or other entry points
        scene_ids = [role['scene_id'] for role in roles]
        if len(scene_ids) != len(set(scene_ids)):
            self.signals.notification_posted.emit("Casting failed: Cannot assign a talent to multiple roles in the same scene.")
            return
        self.scene_service.cast_talent_for_multiple_roles(talent_id, roles)

    def _get_tags_for_planner_by_type(self, tag_type: str) -> Tuple[List[Dict], Set[str], Set[str]]:
        """Helper method to get and process tags of a specific type."""
        tags, categories, orientations = [], set(), set()
        for full_name, tag_data in self.tag_definitions.items():
            if tag_data.get('type') == tag_type:
                cats_raw = tag_data.get('categories', [])
                cats = [cats_raw] if isinstance(cats_raw, str) else cats_raw
                categories.update(cats)
                
                if orientation := tag_data.get('orientation'):
                    orientations.add(orientation)
                
                tag_data_with_name = tag_data.copy()
                tag_data_with_name['full_name'] = full_name

                # Special handling for Action tags
                if tag_type == 'Action':
                    count = sum(slot.get('count', slot.get('min_count', 0)) for slot in tag_data.get('slots', []))
                    tag_data_with_name['participant_count'] = count

                tags.append(tag_data_with_name)
        return (tags, categories, orientations)

    def get_thematic_tags_for_planner(self) -> Tuple[List[Dict], Set[str], Set[str]]:
        if not self._cached_thematic_tags_data:
            self._cached_thematic_tags_data = self._get_tags_for_planner_by_type('Thematic')
        return self._cached_thematic_tags_data

    def get_physical_tags_for_planner(self) -> Tuple[List[Dict], Set[str], Set[str]]:
        if not self._cached_physical_tags_data:
            self._cached_physical_tags_data = self._get_tags_for_planner_by_type('Physical')
        return self._cached_physical_tags_data

    def get_action_tags_for_planner(self) -> Tuple[List[Dict], Set[str], Set[str]]:
        if not self._cached_action_tags_data:
            self._cached_action_tags_data = self._get_tags_for_planner_by_type('Action')
        return self._cached_action_tags_data

    def get_resolved_group_data(self, group_name: str) -> Dict: return self.market_service.get_resolved_group_data(group_name)

    def resolve_interactive_event(self, event_id: str, scene_id: int, talent_id: int, choice_id: str) -> None:
        """
        Applies the effects of a player's choice from an interactive event
        and resumes the scene shooting process.
        """
        if not self.scene_event_service or not self.scene_service:
             return
        
        # Delegate the complex resolution logic to the service
        outcome = self.scene_event_service.resolve_interactive_event(event_id, scene_id, talent_id, choice_id)

        # If a new event was chained, stop here. The service already emitted the signal.
        if outcome.get("chained_event_triggered"):
            self.db_session.commit()
            return

        # If the scene was cancelled, the controller now handles calling the deletion service.
        if outcome.get("scene_was_cancelled"):
            # The notification about cost was already sent by the event service.
            # We call delete_scene silently to avoid duplicate messages.
            # We also tell it not to commit, as we'll do that at the end of this method.
            self.delete_scene(scene_id, silent=True)
        else:
            # If the scene was NOT cancelled, continue the shoot.
            self.scene_service._continue_shoot_scene(scene_id, outcome.get("modifiers", {}))

        self.db_session.commit()
        
        # After resolving the event, automatically try to continue the week.
        self.advance_week()

    def _create_hiring_config(self) -> HiringConfig:
        """Creates the HiringConfig object from the data manager."""
        return HiringConfig(
            concurrency_default_limit=self.data_manager.game_config.get("hiring_concurrency_default_limit", 99),
            refusal_threshold=self.data_manager.game_config.get("talent_refusal_threshold", 0.2),
            orientation_refusal_threshold=self.data_manager.game_config.get("talent_orientation_refusal_threshold", 0.1),
            pickiness_popularity_scalar=self.data_manager.game_config.get("pickiness_popularity_scalar", 0.05),
            pickiness_ambition_scalar=self.data_manager.game_config.get("pickiness_ambition_scalar", 0.1),
            base_talent_demand=self.data_manager.game_config.get("base_talent_demand", 400),
            demand_perf_divisor=self.data_manager.game_config.get("hiring_demand_perf_divisor", 200.0),
            median_ambition=self.data_manager.game_config.get("median_ambition_level", 5),
            ambition_demand_divisor=self.data_manager.game_config.get("ambition_to_demand_divisor", 5.0),
            popularity_demand_scalar=self.data_manager.game_config.get("popularity_to_demand_scalar", 0.001),
            minimum_talent_demand=self.data_manager.game_config.get("minimum_talent_demand", 100)
        )

    def _reinitialize_services(self):
        if not self.db_session:
            return
        self.market_service = MarketService(self.db_session, self.data_manager.market_data, self.data_manager.tag_definitions)
        self.role_performance_service = RolePerformanceService(self.data_manager)
        self.talent_service = TalentService(self.db_session, self.data_manager, self.market_service)
        self.hiring_config = self._create_hiring_config()
        self.hire_talent_service = HireTalentService(self.db_session, self.data_manager, self.talent_service, self.role_performance_service, self.hiring_config)
        self.scene_event_service = SceneEventService(self.db_session, self.game_state, self.signals, self.data_manager, self.talent_service)
        self.scene_service = SceneService(self.db_session, self.signals, self.data_manager, self.talent_service, self.market_service, self.role_performance_service, self.scene_event_service)
        self.time_service = TimeService(self.db_session, self.game_state, self.signals, self.scene_service, self.talent_service, self.market_service, self.data_manager)
        self.go_to_list_service = GoToListService(self.db_session, self.signals)
        self.player_settings_service = PlayerSettingsService(self.db_session, self.signals) 
        self.email_service = EmailService(self.db_session, self.signals, self.game_state)

    # --- Game Session Management (Delegated to GameSessionService) ---

    def new_game_started(self):
        """Initializes a new game session."""
        self.game_state, self.db_session, self.current_save_path = self.game_session_service.start_new_game()
        self._reinitialize_services()
        
        # Emit signals to update UI
        self.signals.money_changed.emit(self.game_state.money)
        self.signals.time_changed.emit(self.game_state.week, self.game_state.year)
        self.signals.talent_pool_changed.emit()
        self.signals.new_game_started.emit()
        self.signals.show_main_window_requested.emit()
        
    def load_game(self, save_name):
        """Loads a game session from a file."""
        self.game_state, self.db_session, self.current_save_path = self.game_session_service.load_game(save_name)
        self._reinitialize_services()
        
        # Emit signals to update UI
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
            self.game_state, self.db_session, self.current_save_path = result
            self._reinitialize_services()
            
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
            self.game_state, self.db_session, self.current_save_path = result
            self._reinitialize_services()
            self.signals.show_main_window_requested.emit()

    def return_to_main_menu(self, exit_save: bool):
        """
        Handles returning to the main menu from an active game.
        This method is now the single source of truth for session cleanup in this context.
        """
        if self.db_session:
            # Only perform an exit save if the game is active and not over.
            self.game_session_service.handle_exit_save(exit_save)
            
            # Execute the shutdown sequence in the correct order.
            self.db_session.close()
            self.db_session = None
            self.save_manager.db_manager.disconnect()
            self.save_manager.cleanup_session_file()

        if self.game_over:
            self.game_over = False  # Reset state for the start screen

        self.signals.show_start_screen_requested.emit()

    def quit_game(self, exit_save=False):
        self.game_session_service.handle_exit_save(exit_save)
        self.signals.quit_game_requested.emit()

    def handle_application_shutdown(self):
        """
        Performs final cleanup when the application is closing.
        This is typically called from the main window's closeEvent.
        """
        if self.db_session:
            self.db_session.close()
        self.save_manager.db_manager.disconnect()
        self.save_manager.cleanup_session_file()

    def handle_game_over(self):
        self.game_over = True
        self.signals.show_start_screen_requested.emit()

    def check_for_saves(self) -> bool:
        return self.save_manager.has_saves()
        
    # --- Other Methods ---

    def create_email(self, subject: str, body: str):
        if not self.email_service: return
        self.email_service.create_email(subject, body)

    def get_unread_email_count(self) -> int:
        if not self.email_service: return 0
        return self.email_service.get_unread_email_count()

    def mark_email_as_read(self, email_id: int):
        if not self.email_service: return
        self.email_service.mark_email_as_read(email_id)

    def delete_emails(self, email_ids: list[int]):
        if not self.email_service: return
        self.email_service.delete_emails(email_ids)

    # --- Go-To List Actions (Proxy Methods) ---
    def add_talent_to_go_to_list(self, talent_id: int):
        """Adds a talent to the default 'General' Go-To List category via the service."""
        if not self.go_to_list_service: return
        self.go_to_list_service.add_talent_to_general_category(talent_id)

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