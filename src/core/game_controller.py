import logging
from typing import List, Dict, Optional, Tuple, Set
from PyQt6.QtCore import QObject

from core.service_container import ServiceContainer
from core.game_signals import GameSignals
from data.game_state import *
from data.save_manager import SaveManager
from core.talent_generator import TalentGenerator
from data.data_manager import DataManager
from data.settings_manager import SettingsManager
from ui.theme_manager import Theme, ThemeManager
from database.db_models import TalentDB, SceneDB

from services.query.tag_query_service import TagQueryService
from services.query.game_query_service import GameQueryService
from services.query.talent_query_service import TalentQueryService
from services.query.talent_location_service import TalentLocationService
from services.calculation.tag_validation_checker import TagValidationChecker
from services.calculation.talent_demand_calculator import TalentDemandCalculator
from services.calculation.bloc_cost_calculator import BlocCostCalculator
from services.calculation.shoot_results_calculator import ShootResultsCalculator
from services.calculation.bulk_booking_validator import BulkBookingValidator
from services.tour_sponsorship_preview_service import TourSponsorshipPreviewService
from services.command.talent_command_service import TalentCommandService
from services.command.scene_command_service import SceneCommandService
from services.command.contract_command_service import ContractCommandService
from services.command.casting_command_service import CastingCommandService
from services.command.tour_command_service import TourCommandService
from services.command.scene_event_command_service import SceneEventCommandService
from services.market_service import MarketService
from services.time_service import TimeService
from services.command.go_to_list_service import GoToListService
from services.game_session_service import GameSessionService
from services.player_settings_service import PlayerSettingsService
from services.command.email_service import EmailService
from services.models.results import EventAction, TourSponsorshipPreviewResult, ValidationResult
from utils import time_utils

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
        self._graceful_shutdown_in_progress = False
        
        self.game_constant = self.data_manager.game_config
        self.market_data = self.data_manager.market_data
        self.affinity_data = self.data_manager.affinity_data
        self.tag_definitions = self.data_manager.tag_definitions
        self.generator_data = self.data_manager.generator_data
        self.talent_archetypes = self.data_manager.talent_archetypes
        self.traits_data = self.data_manager.traits_data
        self.help_topics = self.data_manager.help_topics
        
        self.talent_generator = TalentGenerator(self.game_constant, self.generator_data, self.affinity_data, self.tag_definitions, self.talent_archetypes, self.traits_data)
        
        self.game_session_service = GameSessionService(self.save_manager, self.data_manager, self.signals, self.talent_generator)

       # --- Service Properties ---
        self.query_service: Optional[GameQueryService] = None
        self.tag_query_service: Optional['TagQueryService'] = None
        self.tag_validation_checker : Optional[TagValidationChecker] = None
        self.talent_command_service: Optional[TalentCommandService] = None
        self.scene_command_service: Optional[SceneCommandService] = None
        self.contract_command_service: Optional[ContractCommandService] = None
        self.casting_command_service: Optional[CastingCommandService] = None
        self.market_service: Optional[MarketService] = None
        self.talent_location_service: Optional[TalentLocationService] = None
        self.tour_command_service: Optional[TourCommandService] = None
        self.tour_sponsorship_service: Optional[TourSponsorshipPreviewService] = None
        self.talent_query_service: Optional[TalentQueryService] = None
        self.talent_demand_calculator: Optional[TalentDemandCalculator] = None
        self.bloc_cost_calculator: Optional[BlocCostCalculator] = None
        self.shoot_results_calculator: Optional[ShootResultsCalculator] = None
        self.time_service: Optional[TimeService] = None
        self.go_to_list_service: Optional[GoToListService] = None
        self.scene_event_command_service: Optional[SceneEventCommandService] = None
        self.player_settings_service: Optional[PlayerSettingsService] = None
        self.email_service: Optional[EmailService] = None
        
        self.game_over = False

    def get_current_theme(self) -> Theme:
        theme_name = self.settings_manager.get_setting("theme", "dark")
        return self.theme_manager.get_theme(theme_name)

    # --- UI Data Access Methods ---
    def get_talent_by_id(self, talent_id: int) -> Optional[Talent]:
        return self.query_service.get_talent_by_id(talent_id) if self.query_service else None

    def get_talent_schedule_status(self, talent_id: int, year: int):
        if not self.talent_query_service: return []
        return self.talent_query_service.get_talent_schedule_status_for_year(talent_id, year)
    
    def find_available_roles_for_talent(self, talent_id: int) -> List[Dict]:
        if not self.talent_query_service: return []
        return self.talent_query_service.find_available_roles_for_talent(
            talent_id, self.game_state.studio_location, self.game_state.absolute_week
        )

    def calculate_bulk_hiring_costs(self, talent_id: int, roles: List[Dict]) -> Optional[Dict]:
        if not self.talent_demand_calculator or not self.query_service or not self.talent_location_service:
            return None
        talent_dc = self.query_service.get_talent_by_id(talent_id)
        if not talent_dc: return None
        roles_with_context = []
        for role in roles:
            scene_dc = self.query_service.get_scene_by_id(role['scene_id'])
            if not scene_dc: return None
            talent_loc = self.talent_location_service.get_effective_location_at_date(
                talent_id, scene_dc.scheduled_absolute_week
            )
            roles_with_context.append({
                'scene': scene_dc, 'virtual_performer_id': role['virtual_performer_id'],
                'bloc_id': scene_dc.bloc_id, 'talent_effective_location': talent_loc
            })
        return self.talent_demand_calculator.calculate_bulk_hiring_costs(
            talent_dc, roles_with_context, self.game_state.absolute_week
        )

    def calculate_demands_for_multiple_talents(self, talent_ids: List[int], scene_id: int, vp_id: int) -> Dict[int, int]:
        if not self.talent_demand_calculator or not self.query_service or not self.talent_location_service:
            return {talent_id: 0 for talent_id in talent_ids}
        scene = self.query_service.get_scene_by_id(scene_id)
        if not scene: return {talent_id: 0 for talent_id in talent_ids}
        talents = self.query_service.get_multiple_talents_by_ids(talent_ids)
        talent_locations = self.talent_location_service.get_effective_locations_for_multiple_talents(
            talent_ids, scene.scheduled_absolute_week
        )
        demands = {}
        for talent in talents:
            effective_location = talent_locations.get(talent.id, talent.base_location)
            cost_breakdown = self.talent_demand_calculator.calculate_total_demand(
                talent, scene, vp_id, effective_location, self.game_state.absolute_week
            )
            demands[talent.id] = cost_breakdown['total_cost']
        return demands
    
    def get_effective_locations_for_multiple_talents(self, talent_ids: List[int], absolute_week: int) -> Dict[int, str]:
        if not self.talent_location_service: return {}
        return self.talent_location_service.get_effective_locations_for_multiple_talents(talent_ids, absolute_week)

    # --- Game Logic ---
    def advance_week(self):
        if self.game_over: return

        incomplete_scenes = self.query_service.get_incomplete_scenes_for_week(self.game_state.absolute_week)
        if incomplete_scenes:
            self.signals.incomplete_scene_check_requested.emit(incomplete_scenes)
            return

        result = self.time_service.advance_week()

        self.game_state.absolute_week = result.new_absolute_week
        self.game_state.money = result.new_money
        self.save_manager.auto_save()

        if result.was_paused:
            if result.scenes_shot > 0: self.signals.scenes_changed.emit()
            return

        if self.game_state.money <= self.game_constant.get('game_over_threshold', -5000):
            self.signals.game_over_triggered.emit("bankruptcy")
            return

        new_year, new_week = time_utils.from_absolute(result.new_absolute_week)
        self.signals.time_changed.emit(new_week, new_year)
        self.signals.money_changed.emit(self.game_state.money)
        if result.scenes_shot > 0 or result.scenes_edited > 0: self.signals.scenes_changed.emit()
        if result.market_changed: self.signals.market_changed.emit()
        if result.talent_pool_changed: self.signals.talent_pool_changed.emit()

    def create_shooting_bloc(self, absolute_week: int, region: str, num_scenes: int, name: str, set_location: str, visual_style_id: str, department_budgets: Dict[str, int], crew_assignments: Dict[str, Dict], picture_set_settings: Dict[str, Any], policies: List[str]) -> bool:
        if not self.scene_command_service: return False
        return self.scene_command_service.create_shooting_bloc(absolute_week, region, num_scenes, name, set_location, visual_style_id, department_budgets, crew_assignments, picture_set_settings, policies)
    
    def create_blank_scene(self, absolute_week: Optional[int] = None) -> int:
        use_week = absolute_week if absolute_week is not None else self.game_state.absolute_week
        return self.scene_command_service.create_blank_scene(use_week)

    # --- Game Session Management ---
    def _on_session_loaded(self, result: Optional[Tuple[GameState, str]]):
        """Helper to handle common setup after a game is loaded or started."""
        if result:
            self.game_state, self.current_save_path = result
            self.service_container.initialize_and_populate_services(self, self.game_state)
            
            self.signals.money_changed.emit(self.game_state.money)
            year, week = time_utils.from_absolute(self.game_state.absolute_week)
            self.signals.time_changed.emit(week, year)
            self.signals.scenes_changed.emit()
            self.signals.talent_pool_changed.emit()
            self.signals.emails_changed.emit()
            self.signals.show_main_window_requested.emit()

    def new_game_started(self):
        result = self.game_session_service.start_new_game()
        self._on_session_loaded(result)
        if result:
            self.signals.new_game_started.emit()

    def load_game(self, save_name: str):
        result = self.game_session_service.load_game(save_name)
        self._on_session_loaded(result)

    def continue_game(self):
        result = self.game_session_service.continue_game()
        self._on_session_loaded(result)

    def quick_load(self):
        result = self.game_session_service.quick_load()
        self._on_session_loaded(result)
        
    def get_blocs_for_schedule_view(self, year: int) -> List[ShootingBloc]:
        if not self.query_service: return []
        return self.query_service.get_blocs_for_schedule_view(year)

    # Pass-through methods that don't need modification from original...
    def get_current_theme(self) -> Theme:
        theme_name = self.settings_manager.get_setting("theme", "dark")
        return self.theme_manager.get_theme(theme_name)
    def get_available_ethnicities(self) -> list[str]: return self.data_manager.get_available_ethnicities() if self.data_manager else []
    def get_ethnicity_hierarchy(self) -> Dict[str, List[str]]: return self.data_manager.get_ethnicity_hierarchy() if self.data_manager else {}
    def get_available_nationalities(self) -> List[str]: return self.data_manager.get_available_nationalities() if self.data_manager else []
    def get_location_to_region_map(self) -> Dict[str, str]: return self.data_manager.get_location_to_region_map() if self.data_manager else {}
    def get_locations_by_region(self) -> Dict[str, List[str]]: return self.data_manager.get_locations_by_region() if self.data_manager else {}
    def get_available_cup_sizes(self) -> list[str]: return self.data_manager.get_available_cup_sizes()
    def get_multiple_talents_by_ids(self, talent_ids: List[int]) -> List[Talent]: return self.query_service.get_multiple_talents_by_ids(talent_ids) if self.query_service else []
    def get_filtered_talents(self, filters: dict) -> List[Talent]: return self.query_service.get_filtered_talents(filters) if self.query_service else []
    def get_bloc_by_id(self, bloc_id: int) -> Optional[ShootingBloc]: return self.query_service.get_bloc_by_id(bloc_id) if self.query_service else None
    def get_scene_by_id(self, scene_id: int) -> Optional[Scene]: return self.query_service.get_scene_by_id(scene_id) if self.query_service else None
    def get_multiple_scenes_by_ids(self, scene_ids: List[int]) -> List[Scene]: return self.query_service.get_multiple_scenes_by_ids(scene_ids) if self.query_service else []
    def get_shot_scenes(self) -> List[Scene]: return self.query_service.get_shot_scenes() if self.query_service else []
    def get_all_market_states(self) -> Dict[str, MarketGroupState]: return self.query_service.get_all_market_states() if self.query_service else {}
    def get_scene_history_for_talent(self, talent_id: int) -> List[Scene]: return self.query_service.get_scene_history_for_talent(talent_id) if self.query_service else []
    def get_castable_scenes(self) -> List[Dict]: return self.query_service.get_castable_scenes_for_ui() if self.query_service else []
    def get_uncast_roles_for_scene(self, scene_id: int) -> List[Dict]: return self.query_service.get_uncast_roles_for_scene_ui(scene_id) if self.query_service else []
    def get_talent_chemistry(self, talent_id: int) -> Dict[int, Dict]: return self.query_service.get_talent_chemistry(talent_id) if self.query_service else {}

    def get_talent_tours_for_year(self, talent_id: int, year: int) -> List[Tour]: return self.talent_query_service.get_talent_tours_for_year(talent_id, year) if self.talent_query_service else []
    def get_go_to_list_talents(self) -> List[Talent]: return self.query_service.get_all_talents_in_go_to_lists() if self.query_service else []
    def get_go_to_list_categories(self) -> List[Dict]: return self.query_service.get_all_categories() if self.query_service else []
    def get_talents_in_go_to_category(self, category_id: int) -> List[Talent]: return self.query_service.get_talents_in_category(category_id) if self.query_service else []
    def get_talent_go_to_categories(self, talent_id: int) -> List[Dict]: return self.query_service.get_talent_categories(talent_id) if self.query_service else []
    def get_all_emails(self) -> List[EmailMessage]: return self.query_service.get_all_emails() if self.query_service else []
    def start_editing_scene(self, scene_id: int, editing_tier_id: str): self.scene_command_service.start_editing_scene(scene_id, editing_tier_id)
    def release_scene(self, scene_id: int):
        result = self.scene_command_service.release_scene(scene_id)
        if not result: return
        self.signals.notification_posted.emit(f"'{result['title']}' released! Revenue: +${result['revenue']:,}")
        self.signals.scenes_changed.emit()
        self.signals.money_changed.emit(result['new_money'])
        self.signals.market_changed.emit()
        if result['market_changed']:
            for group_name in result['discoveries']: self.signals.notification_posted.emit(f"New market insights gained for '{group_name}'!")
    def calculate_shooting_bloc_cost(self, num_scenes: int, settings: Dict, policies: List[str]) -> int: return self.bloc_cost_calculator.calculate_shooting_bloc_cost(num_scenes, settings, policies) if self.bloc_cost_calculator else 0
    def delete_scene(self, scene_id: int, penalty_percentage: float = 0.0): self.scene_command_service.delete_scene(scene_id, penalty_percentage)
    def update_scene_full(self, scene_data: Scene) -> Dict: return self.scene_command_service.update_scene_full(scene_data)
    def get_eligible_talent_for_role(self, scene_id: int, vp_id: int, filters: dict = None) -> List[TalentDB]: return self.talent_query_service.get_eligible_talent_for_role(scene_id, vp_id, filters) if self.talent_query_service else []
    def get_role_details_for_ui(self, scene_id: int, vp_id: int) -> Dict: return self.talent_query_service.get_role_details_for_ui(scene_id, vp_id) if self.talent_query_service else {}
    def calculate_contract_salary(self, talent_id: int, terms: Dict) -> int:
        if not self.talent_demand_calculator or not self.query_service: return 0
        talent = self.query_service.get_talent_by_id(talent_id)
        if not talent: return 0
        return self.talent_demand_calculator.calculate_contract_salary(talent, terms)
    def sign_contract(self, talent_id: int, terms: Dict):
        if not self.contract_command_service or not self.talent_demand_calculator or not self.query_service: return
        talent = self.query_service.get_talent_by_id(talent_id)
        if not talent: return
        salary = self.talent_demand_calculator.calculate_contract_salary(talent, terms)
        self.contract_command_service.sign_contract(talent_id, terms, salary)
    def cast_talent_for_virtual_performer(self, talent_id: int, scene_id: int, virtual_performer_id: int, cost: int): self.casting_command_service.cast_talent_for_role(talent_id, scene_id, virtual_performer_id, cost)
    def cast_talent_for_multiple_roles(self, talent_id: int, hiring_data: Dict):
        scene_ids = [role['scene_id'] for role in hiring_data['roles']]
        if len(scene_ids) != len(set(scene_ids)):
            self.signals.notification_posted.emit("Casting failed: Cannot assign a talent to multiple roles in the same scene.")
            return
        self.casting_command_service.cast_talent_for_multiple_roles(talent_id, hiring_data)
    def get_tour_sponsorship_preview(self, talent_id: int, roles: List[Dict]) -> TourSponsorshipPreviewResult:
        if not self.tour_sponsorship_service: return TourSponsorshipPreviewResult(is_feasible=False, refusal_reason="Tour calculation service not available.")
        studio_location = self.game_state.studio_location
        return self.tour_sponsorship_service.generate_preview(talent_id, roles, studio_location)
    def sponsor_tour(self, talent_id: int, roles_to_cast: list, tour_details: dict, total_upfront_cost: int):
        if not self.tour_command_service: return
        self.tour_command_service.sponsor_tour(talent_id, roles_to_cast, tour_details, total_upfront_cost)
    def get_thematic_tags_for_planner(self) -> Tuple[List[Dict], Set[str], Set[str]]: return self.tag_query_service.get_tags_for_planner('Thematic')
    def get_physical_tags_for_planner(self) -> Tuple[List[Dict], Set[str], Set[str]]: return self.tag_query_service.get_tags_for_planner('Physical')
    def get_action_tags_for_planner(self) -> Tuple[List[Dict], Set[str], Set[str]]: return self.tag_query_service.get_tags_for_planner('Action')
    def get_unique_contract_options(self, gender: str) -> Tuple[List[str], List[str]]: return self.tag_query_service.get_unique_contract_options(gender) if self.tag_query_service else ([], [])
    def is_performer_eligible_for_tag(self, performer, tag_name: str) -> bool:
        if not self.tag_validation_checker or not self.tag_query_service: return False
        tag_def = self.tag_query_service.get_tag_definition(tag_name)
        if not tag_def: return False
        return self.tag_validation_checker.is_performer_eligible_for_tag(performer, tag_def)
    def get_resolved_group_data(self, group_name: str) -> Dict: return self.market_service.get_resolved_group_data(group_name)
    def resolve_interactive_event(self, event_id: str, scene_id: int, talent_id: int, choice_id: str) -> None:
        if not self.scene_event_command_service or not self.scene_command_service: return
        result = self.scene_event_command_service.resolve_interactive_event(event_id, scene_id, talent_id, choice_id)
        if result.notification: self.signals.notification_posted.emit(result.notification)
        if result.next_action == EventAction.CANCEL_SCENE:
            self.scene_command_service.delete_scene(scene_id, result.cancellation_penalty)
            self.advance_week()
        elif result.next_action == EventAction.CHAIN_EVENT:
            payload = result.chained_event_payload
            self.signals.interactive_event_triggered.emit(payload['event_data'], payload['scene_id'], payload['talent_id'])
        elif result.next_action == EventAction.CONTINUE_SHOOT:
            self.scene_command_service.continue_shoot_scene_after_event(scene_id, result.shoot_modifiers)
            self.advance_week()
    def save_game(self, save_name: str): self.game_session_service.save_game(save_name)
    def delete_save_file(self, save_name: str) -> bool: return self.game_session_service.delete_save(save_name)
    def quick_save(self): self.game_session_service.quick_save()
    def return_to_main_menu(self, exit_save: bool):
        self._graceful_shutdown_in_progress = True
        self.game_session_service.handle_exit_save(exit_save and not self.game_over)
        self.service_container.cleanup_services(self)
        self.current_save_path = None
        self.game_over = False
        self._graceful_shutdown_in_progress = False
        self.signals.show_start_screen_requested.emit()
    def quit_game(self, exit_save: bool = False):
        self._graceful_shutdown_in_progress = True
        self.game_session_service.handle_exit_save(exit_save and not self.game_over)
        self.service_container.cleanup_services(self)
        self._graceful_shutdown_in_progress = False
        self.signals.quit_game_requested.emit()
    def handle_application_shutdown(self):
        if self.current_save_path and not self._graceful_shutdown_in_progress: self.service_container.cleanup_services(self)
    def handle_game_over(self):
        self.game_over = True
        self.service_container.cleanup_services(self)
        self.current_save_path = None
        self.signals.game_over_triggered.emit("Your studio has gone bankrupt.")
    def check_for_saves(self) -> bool: return self.game_session_service.has_saves()
    def get_unread_email_count(self) -> int: return self.query_service.get_unread_email_count() if self.query_service else 0
    def mark_email_as_read(self, email_id: int):
        if not self.email_service: return
        self.email_service.mark_email_as_read(email_id)
    def delete_emails(self, email_ids: list[int]):
        if not self.email_service: return
        self.email_service.delete_emails(email_ids)
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
    def get_favorite_tags(self, tag_type: str) -> List[str]: return self.player_settings_service.get_favorite_tags(tag_type) if self.player_settings_service else []
    def toggle_favorite_tag(self, tag_name: str, tag_type: str):
        if not self.player_settings_service: return
        self.player_settings_service.toggle_favorite_tag(tag_name, tag_type)
    def reset_favorite_tags(self, tag_type: str):
        if not self.player_settings_service: return
        self.player_settings_service.reset_favorite_tags(tag_type)
    def validate_potential_bookings(self, talent_id: int, roles_data: List[Dict]) -> Dict[Tuple[int, int], ValidationResult]:
        if not self.query_service or not self.talent_query_service or not self.shoot_results_calculator or not self.talent_demand_calculator: return {}
        talent = self.query_service.get_talent_by_id(talent_id)
        if not talent: return {}
        
        # This part needs fixing because we can't just get bookings for one year
        # A quick fix is to get all bookings for all time, which is inefficient.
        # A better fix would be to get bookings for a range of years.
        # For now, let's assume the UI won't allow booking too far in the future
        # and just get bookings for the current and next year.
        current_absolute_week = self.game_state.absolute_week
        current_year, _ = time_utils.from_absolute(current_absolute_week)
        
        start_abs_week_current_year = time_utils.to_absolute(current_year, 1)
        end_abs_week_next_year = time_utils.to_absolute(current_year + 1, 52)
        
        all_bookings_map = self.talent_query_service.get_talent_bookings_by_absolute_week(
            talent.id, start_abs_week_current_year, end_abs_week_next_year
        )
        
        existing_bookings = []
        for week_bookings in all_bookings_map.values():
            existing_bookings.extend(week_bookings)
        
        validator = BulkBookingValidator(
            current_absolute_week=self.game_state.absolute_week,
            talent=talent,
            existing_bookings=existing_bookings,
            hiring_config=self.talent_demand_calculator.hiring_config,
            shoot_calculator=self.shoot_results_calculator
        )

        scene_ids = [r['scene_id'] for r in roles_data]
        scenes_map = {s.id: s for s in self.get_multiple_scenes_by_ids(scene_ids)}

        results = {}
        for role in roles_data:
            scene = scenes_map.get(role['scene_id'])
            if not scene:
                results[(role['scene_id'], role['virtual_performer_id'])] = ValidationResult(False, "Scene not found")
                continue
            
            result = validator.try_book_role(scene, role['virtual_performer_id'])
            results[(role['scene_id'], role['virtual_performer_id'])] = result
            
        return results