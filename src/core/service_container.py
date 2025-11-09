import logging
from typing import Optional, TYPE_CHECKING

from core.game_signals import GameSignals
from data.data_manager import DataManager
from data.save_manager import SaveManager
from data.game_state import GameState
from services.command.email_service import EmailService
from services.game_session_service import GameSessionService
from services.command.go_to_list_service import GoToListService
from services.market_service import MarketService
from services.player_settings_service import PlayerSettingsService
from services.time_service import TimeService
from services.calculation.tag_validation_checker import TagValidationChecker
from services.calculation.post_production_calculator import PostProductionCalculator
from services.calculation.revenue_calculator import RevenueCalculator
from services.command.scene_processing_service import SceneProcessingService
from services.calculation.scene_quality_calculator import SceneQualityCalculator
from services.calculation.shoot_results_calculator import ShootResultsCalculator
from services.calculation.talent_demand_calculator import TalentDemandCalculator
from services.command.scene_command_service import SceneCommandService
from services.command.talent_command_service import TalentCommandService
from services.command.scene_event_command_service import SceneEventCommandService
from services.events.scene_event_trigger_service import SceneEventTriggerService
from services.models.configs import HiringConfig, MarketConfig, SceneCalculationConfig
from services.query.game_query_service import GameQueryService
from services.query.talent_query_service import TalentQueryService
from services.query.tag_query_service import TagQueryService
from services.calculation.market_group_resolver import MarketGroupResolver
from services.calculation.role_performance_calculator import RolePerformanceCalculator
from services.calculation.talent_availability_checker import TalentAvailabilityChecker
from services.calculation.talent_affinity_calculator import TalentAffinityCalculator
from services.calculation.bloc_cost_calculator import BlocCostCalculator

if TYPE_CHECKING:
    from core.game_controller import GameController

logger = logging.getLogger(__name__)

class ServiceContainer:
    """
    Acts as a Composition Root for the application's service layer.
    This class is responsible for creating, configuring, and managing the
    lifecycle of all services.
    """
    def __init__(self, data_manager: DataManager, save_manager: SaveManager, signals: GameSignals):
        self.data_manager = data_manager
        self.save_manager = save_manager
        self.signals = signals

        # Config objects
        self.hiring_config: Optional[HiringConfig] = None
        self.scene_calc_config: Optional[SceneCalculationConfig] = None
        self.market_config: Optional[MarketConfig] = None

        # Service instances
        self.query_service: Optional[GameQueryService] = None
        self.tag_query_service: Optional[TagQueryService] = None
        self.talent_command_service: Optional[TalentCommandService] = None
        self.scene_command_service: Optional[SceneCommandService] = None
        self.market_service: Optional[MarketService] = None
        self.talent_query_service: Optional[TalentQueryService] = None
        self.bloc_cost_calculator: Optional[BlocCostCalculator] = None
        self.talent_demand_calculator: Optional[TalentDemandCalculator] = None
        self.role_performance_calculator: Optional[RolePerformanceCalculator] = None
        self.tag_validation_checker: Optional[TagValidationChecker] = None
        self.talent_affinity_calculator: Optional[TalentAffinityCalculator] = None
        self.availability_checker: Optional[TalentAvailabilityChecker] = None
        self.shoot_results_calculator: Optional[ShootResultsCalculator] = None
        self.scene_quality_calculator: Optional[SceneQualityCalculator] = None
        self.post_production_calculator: Optional[PostProductionCalculator] = None
        self.revenue_calculator: Optional[RevenueCalculator] = None
        self.scene_processing_service: Optional[SceneProcessingService] = None
        self.time_service: Optional[TimeService] = None
        self.go_to_list_service: Optional[GoToListService] = None
        self.scene_event_trigger_service: Optional[SceneEventTriggerService] = None
        self.scene_event_command_service: Optional[SceneEventCommandService] = None
        self.player_settings_service: Optional[PlayerSettingsService] = None
        self.email_service: Optional[EmailService] = None

    def initialize_and_populate_services(self, controller: 'GameController', game_state: GameState):
        """
        Creates all service instances and injects them into the controller.
        This is the main entry point for starting a game session's services.
        """
        logger.info("Initializing service layer...")
        # Get the session factory from the database manager
        session_factory = self.save_manager.db_manager.get_session_factory()
        
        # --- Create Configs ---
        self._create_configs()

        # --- Create Services ---
        market_resolver = MarketGroupResolver(self.data_manager.market_data)
        self.market_service = MarketService(market_resolver, self.data_manager.tag_definitions, config=self.market_config)
        self.talent_affinity_calculator = TalentAffinityCalculator(self.scene_calc_config)
        self.availability_checker = TalentAvailabilityChecker(self.data_manager, self.hiring_config)
        self.query_service = GameQueryService(session_factory)
        self.tag_query_service = TagQueryService(self.data_manager)
        self.talent_command_service = TalentCommandService(self.signals, self.scene_calc_config, self.talent_affinity_calculator)
        self.talent_demand_calculator = TalentDemandCalculator(session_factory, self.data_manager, self.query_service, self.hiring_config, self.availability_checker)
        self.bloc_cost_calculator = BlocCostCalculator(self.data_manager)
        self.talent_query_service = TalentQueryService(session_factory, self.data_manager, self.talent_demand_calculator, self.query_service, self.hiring_config, self.availability_checker)
        self.role_performance_calculator = RolePerformanceCalculator()
        self.player_settings_service = PlayerSettingsService(session_factory, self.signals)
        self.go_to_list_service = GoToListService(session_factory, self.signals)
        self.email_service = EmailService(session_factory, self.signals, game_state)
        self.tag_validation_checker = TagValidationChecker(self.data_manager)
        self.shoot_results_calculator = ShootResultsCalculator(self.data_manager, self.scene_calc_config, self.role_performance_calculator)
        self.scene_quality_calculator = SceneQualityCalculator(self.data_manager, self.scene_calc_config)
        self.post_production_calculator = PostProductionCalculator(self.data_manager)
        self.revenue_calculator = RevenueCalculator(self.data_manager, self.scene_calc_config)
        self.scene_processing_service = SceneProcessingService(
            self.data_manager, self.talent_command_service, self.scene_calc_config,
            self.tag_validation_checker, self.shoot_results_calculator,
            self.scene_quality_calculator, self.post_production_calculator
        )
        self.scene_event_trigger_service = SceneEventTriggerService(self.data_manager)
        self.scene_command_service = SceneCommandService(
            session_factory, self.signals, self.data_manager, self.query_service, self.talent_command_service,
            self.market_service, self.email_service, self.scene_processing_service, self.revenue_calculator,
            self.scene_event_trigger_service, self.bloc_cost_calculator
        )
        self.scene_event_command_service = SceneEventCommandService(session_factory, self.data_manager, self.query_service)
        self.time_service = TimeService(session_factory, self.signals, self.scene_command_service, self.talent_command_service, self.market_service)

        # --- Populate Controller ---
        self._populate_controller(controller)
        logger.info("Service layer initialized and controller populated.")

    def cleanup_services(self, controller: 'GameController'):
        """
        Properly cleans up an active game session by nullifying services,
        which releases database references, and then cleaning the session file.
        """
        logger.info("Starting service layer cleanup process...")
        # 1. Nullify services on the controller to break reference cycles
        self._clear_controller_services(controller)

        # 2. Nullify services on the container to release all references
        self._clear_container_services()

        # 3. Delegate file cleanup to the SaveManager.
        self.save_manager.cleanup_session_file()
        logger.info("Service layer cleanup complete.")

    def _populate_controller(self, controller: 'GameController'):
        """Injects the initialized services into the controller instance."""
        controller.query_service = self.query_service
        controller.tag_query_service = self.tag_query_service
        controller.tag_validation_checker = self.tag_validation_checker
        controller.talent_command_service = self.talent_command_service
        controller.scene_command_service = self.scene_command_service
        controller.market_service = self.market_service
        controller.talent_demand_calculator = self.talent_demand_calculator
        controller.bloc_cost_calculator = self.bloc_cost_calculator
        controller.talent_query_service = self.talent_query_service
        controller.time_service = self.time_service
        controller.go_to_list_service = self.go_to_list_service
        controller.scene_event_command_service = self.scene_event_command_service
        controller.player_settings_service = self.player_settings_service
        controller.email_service = self.email_service
        # Inject other services as needed by the controller
    
    def _clear_controller_services(self, controller: 'GameController'):
        """Sets all service references on the controller to None."""
        controller.query_service = None
        controller.tag_query_service = None
        controller.tag_validation_checker = None
        controller.talent_command_service = None
        controller.scene_command_service = None
        controller.market_service = None
        controller.talent_demand_calculator = None
        controller.bloc_cost_calculator = None
        controller.talent_query_service = None
        controller.time_service = None
        controller.go_to_list_service = None
        controller.scene_event_command_service = None
        controller.player_settings_service = None
        controller.email_service = None

    def _clear_container_services(self):
        """Sets all service references on this container to None."""
        self.query_service = None
        self.tag_query_service = None
        self.talent_command_service = None
        self.scene_command_service = None
        self.market_service = None
        self.talent_demand_calculator = None
        self.bloc_cost_calculator
        self.talent_query_service = None
        self.role_performance_calculator = None
        self.tag_validation_checker = None
        self.talent_affinity_calculator = None
        self.availability_checker = None
        self.shoot_results_calculator = None
        self.scene_quality_calculator = None
        self.post_production_calculator = None
        self.revenue_calculator = None
        self.scene_processing_service = None
        self.time_service = None
        self.go_to_list_service = None
        self.scene_event_trigger_service = None
        self.scene_event_command_service = None
        self.player_settings_service = None
        self.email_service = None

    def _create_configs(self):
        """Creates all configuration dataclasses from the data manager."""
        game_config = self.data_manager.game_config

        self.market_config = MarketConfig(
            saturation_recovery_rate=game_config.get("market_saturation_recovery_rate", 0.05),
            discovery_interest_threshold=game_config.get("market_discovery_interest_threshold", 1.5),
            discoveries_per_scene=game_config.get("market_discoveries_per_scene", 2)
        )

        self.hiring_config = HiringConfig(
            concurrency_default_limit=game_config.get("hiring_concurrency_default_limit", 99),
            refusal_threshold=game_config.get("talent_refusal_threshold", 0.2),
            orientation_refusal_threshold=game_config.get("talent_orientation_refusal_threshold", 0.1),
            pickiness_popularity_scalar=game_config.get("pickiness_popularity_scalar", 0.05),
            pickiness_ambition_scalar=game_config.get("pickiness_ambition_scalar", 0.1),
            base_talent_demand=game_config.get("base_talent_demand", 400),
            demand_perf_divisor=game_config.get("hiring_demand_perf_divisor", 200.0),
            median_ambition=game_config.get("median_ambition_level", 5),
            ambition_demand_divisor=game_config.get("ambition_to_demand_divisor", 5.0),
            popularity_demand_scalar=game_config.get("popularity_to_demand_scalar", 0.001),
            minimum_talent_demand=game_config.get("minimum_talent_demand", 100)
        )
        
        ds_weights_str_keys = game_config.get("scene_quality_ds_weights", {})
        ds_weights_int_keys = {int(k): v for k, v in ds_weights_str_keys.items()}

        self.scene_calc_config = SceneCalculationConfig(
            stamina_to_pool_multiplier=game_config.get("stamina_to_pool_multiplier", 5),
            base_fatigue_weeks=game_config.get("base_fatigue_weeks", 2),
            in_scene_penalty_scalar=game_config.get("in_scene_penalty_scalar", 0.4),
            fatigue_penalty_scalar=game_config.get("fatigue_penalty_scalar", 0.3),
            maximum_skill_level=game_config.get("maximum_skill_level", 100.0),
            scene_quality_base_acting_weight=game_config.get("scene_quality_base_acting_weight", 0.3),
            scene_quality_min_acting_weight=game_config.get("scene_quality_min_acting_weight", 0.2),
            scene_quality_max_acting_weight=game_config.get("scene_quality_max_acting_weight", 0.8),
            protagonist_contribution_weight=game_config.get("protagonist_contribution_weight", 1.25),
            chemistry_performance_scalar=game_config.get("chemistry_performance_scalar", 0.125),
            scene_quality_ds_weights=ds_weights_int_keys,
            scene_quality_min_performance_modifier=game_config.get("scene_quality_min_performance_modifier", 0.1),
            scene_quality_auto_tag_default_quality=game_config.get("scene_quality_auto_tag_default_quality", 100.0),
            base_release_revenue=game_config.get("base_release_revenue", 50000),
            star_power_revenue_scalar=game_config.get("star_power_revenue_scalar", 0.005),
            saturation_spend_rate=game_config.get("saturation_spend_rate", 0.15),
            default_sentiment_multiplier=game_config.get("default_sentiment_multiplier", 1.0),
            revenue_weight_focused_physical_tag=game_config.get("revenue_weight_focused_physical_tag", 5.0),
            revenue_weight_default_action_appeal=game_config.get("revenue_weight_default_action_appeal", 10.0),
            revenue_weight_auto_tag=game_config.get("revenue_weight_auto_tag", 1.5),
            revenue_penalties=game_config.get("revenue_penalties", {}),
            skill_gain_base_rate=game_config.get("skill_gain_base_rate", 0.02),
            skill_gain_curve_steepness=game_config.get("skill_gain_curve_steepness", 1.5),
            exp_gain_base_rate=game_config.get("experience_gain_base_rate", 0.05),
            exp_gain_curve_steepness=game_config.get("experience_gain_curve_steepness", 2.0),
            ds_skill_gain_base_rate=game_config.get("ds_skill_gain_base_rate", 0.015),
            ds_skill_gain_disposition_multiplier=game_config.get("ds_skill_gain_disposition_multiplier", 1.5),
            ds_skill_gain_dynamic_level_multipliers={int(k): v for k, v in game_config.get("ds_skill_gain_dynamic_level_multipliers", {}).items()},
            age_based_affinity_rules=game_config.get("age_based_affinity_rules", []),
            popularity_gain_scalar=game_config.get("popularity_gain_scalar", 0.05)
        )