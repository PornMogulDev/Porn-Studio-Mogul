import logging
from typing import Optional, TYPE_CHECKING

from core.game_signals import GameSignals

# Data
from data.data_manager import DataManager
from data.save_manager import SaveManager
from data.game_state import GameState

# Command
from services.game_session_service import GameSessionService
from services.command.email_service import EmailService
from services.command.go_to_list_service import GoToListService
from services.command.scene_command_service import SceneCommandService
from services.command.contract_command_service import ContractCommandService
from services.command.casting_command_service import CastingCommandService
from services.command.talent_command_service import TalentCommandService
from services.command.scene_event_command_service import SceneEventCommandService
from services.command.scene_processing_service import SceneProcessingService
from services.command.tour_command_service import TourCommandService
from services.command.studio_command_service import StudioCommandService
from services.command.ai_studio_command_service import AIStudioCommandService

# Calculation
from services.calculation.market_group_resolver import MarketGroupResolver
from services.calculation.role_performance_calculator import RolePerformanceCalculator
from services.calculation.talent_availability_checker import TalentAvailabilityChecker
from services.calculation.talent_affinity_calculator import TalentAffinityCalculator
from services.calculation.bloc_cost_calculator import BlocCostCalculator
from services.calculation.tour_interest_calculator import TourInterestCalculator
from services.calculation.budget_efficiency_calculator import BudgetEfficiencyCalculator
from services.calculation.stress_calculator import StressCalculator
from services.calculation.crew_skill_calculator import CrewSkillCalculator
from services.calculation.bloc_simulation_calculator import BlocSimulationCalculator
from services.calculation.tag_validation_checker import TagValidationChecker
from services.calculation.post_production_calculator import PostProductionCalculator
from services.calculation.revenue_calculator import RevenueCalculator
from services.calculation.scene_quality_calculator import SceneQualityCalculator
from services.calculation.shoot_results_calculator import ShootResultsCalculator
from services.calculation.talent_demand_calculator import TalentDemandCalculator
from services.calculation.upfront_tour_cost_calculator import UpfrontTourCostCalculator
from services.calculation.trait_modifier_resolver import TraitModifierResolver
from services.calculation.talent_status_calculator import TalentStatusCalculator
from services.ai.ai_studio_director import AIStudioDirector

# Events
from services.events.scene_event_trigger_service import SceneEventTriggerService

# Query
from services.query.game_query_service import GameQueryService
from services.query.talent_query_service import TalentQueryService
from services.query.tag_query_service import TagQueryService
from services.query.talent_location_service import TalentLocationService

#Builders
from services.builders.call_sheet_builder import ShootingBlocBuilder
from services.builders.scene_state_editor import SceneStateEditor

# Generators
from core.talent_generator import TalentGenerator
from core.ai_studio_generator import AIStudioGenerator

from services.models.configs import (
    HiringConfig, MarketConfig, SceneCalculationConfig, ContractConfig,
    TourConfig, ProductionConfig
)
from services.market_service import MarketService
from services.player_settings_service import PlayerSettingsService
from services.time_service import TimeService
from services.tour_feasibility_service import TourFeasibilityService
from services.tour_sponsorship_preview_service import TourSponsorshipPreviewService

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

        # --- Config objects ---
        self.hiring_config: Optional[HiringConfig] = None
        self.scene_calc_config: Optional[SceneCalculationConfig] = None
        self.market_config: Optional[MarketConfig] = None
        self.contract_config: Optional[ContractConfig] = None
        self.tour_config: Optional[TourConfig] = None
        self.production_config: Optional[ProductionConfig] = None

        # --- Service instances ---

        # Generators & Lifecycle (Initialized in __init__)
        self.talent_generator: TalentGenerator
        self.ai_studio_generator: AIStudioGenerator
        self.game_session_service: GameSessionService

        # Command
        self.talent_command_service: Optional[TalentCommandService] = None
        self.scene_command_service: Optional[SceneCommandService] = None
        self.casting_command_service: Optional[CastingCommandService] = None
        self.contract_command_service: Optional[ContractCommandService] = None
        self.tour_command_service: Optional[TourCommandService] = None
        self.email_service: Optional[EmailService] = None
        self.studio_command_service: Optional[StudioCommandService] = None
        self.scene_processing_service: Optional[SceneProcessingService] = None
        self.go_to_list_service: Optional[GoToListService] = None
        self.scene_event_command_service: Optional[SceneEventCommandService] = None
        self.ai_studio_command_service: Optional[AIStudioCommandService] = None

        # Calculation
        self.trait_modifier_resolver: Optional[TraitModifierResolver] = None
        self.tour_interest_calculator: Optional[TourInterestCalculator] = None
        self.bloc_cost_calculator: Optional[BlocCostCalculator] = None
        self.talent_demand_calculator: Optional[TalentDemandCalculator] = None
        self.tag_validation_checker: Optional[TagValidationChecker] = None
        self.talent_affinity_calculator: Optional[TalentAffinityCalculator] = None
        self.talent_status_calculator: Optional[TalentStatusCalculator] = None
        self.role_performance_calculator: Optional[RolePerformanceCalculator] = None
        self.upfront_tour_calculator: Optional[UpfrontTourCostCalculator] = None
        self.shoot_results_calculator: Optional[ShootResultsCalculator] = None
        self.scene_quality_calculator: Optional[SceneQualityCalculator] = None
        self.post_production_calculator: Optional[PostProductionCalculator] = None
        self.revenue_calculator: Optional[RevenueCalculator] = None
        self.availability_checker: Optional[TalentAvailabilityChecker] = None
        self.budget_efficiency_calculator: Optional[BudgetEfficiencyCalculator] = None
        self.stress_calculator: Optional[StressCalculator] = None
        self.crew_skill_calculator: Optional[CrewSkillCalculator] = None
        self.bloc_simulation_calculator: Optional[BlocSimulationCalculator] = None
        self.ai_studio_director: Optional[AIStudioDirector] = None

        # Query
        self.query_service: Optional[GameQueryService] = None
        self.tag_query_service: Optional[TagQueryService] = None
        self.talent_query_service: Optional[TalentQueryService] = None
        self.talent_location_service: Optional[TalentLocationService] = None

        # Events
        self.scene_event_trigger_service: Optional[SceneEventTriggerService] = None
        
        self.market_service: Optional[MarketService] = None
        self.player_settings_service: Optional[PlayerSettingsService] = None
        self.tour_feasibility_service: Optional[TourFeasibilityService] = None
        self.tour_sponsorship_service: Optional[TourSponsorshipPreviewService] = None
        self.time_service: Optional[TimeService] = None
        
        # --- Create Configs ---
        self._create_configs()

        # --- Phase 1: App Startup (Generators & Lifecycle) ---
        self.talent_generator = TalentGenerator(
            self.data_manager.game_config, self.data_manager.generator_data, 
            self.data_manager.affinity_data, self.data_manager.tag_definitions, 
            self.data_manager.talent_archetypes, self.data_manager.traits_data
        )
        self.ai_studio_generator = AIStudioGenerator(self.data_manager)

        self.game_session_service = GameSessionService(
            self.save_manager, self.data_manager, self.signals,
            self.talent_generator, self.ai_studio_generator
        )

    def initialize_and_populate_services(self, controller: 'GameController', game_state: GameState):
        """
        Creates all service instances and injects them into the controller.
        This is the main entry point for starting a game session's services.
        """
        logger.info("Initializing service layer...")
        # Get the session factory from the database manager
        session_factory = self.save_manager.db_manager.get_session_factory()

        # --- Create Services (Order Matters for Dependencies) ---
        # Level 0: No dependencies on other services
        market_resolver = MarketGroupResolver(self.data_manager.market_data)
        self.role_performance_calculator = RolePerformanceCalculator()
        self.talent_location_service = TalentLocationService(session_factory)
        self.upfront_tour_calculator = UpfrontTourCostCalculator(self.data_manager)
        self.trait_modifier_resolver = TraitModifierResolver(self.data_manager)
        self.talent_status_calculator = TalentStatusCalculator(self.hiring_config, self.tour_config)
        self.budget_efficiency_calculator = BudgetEfficiencyCalculator(self.production_config)
        self.stress_calculator = StressCalculator(self.data_manager, self.scene_calc_config, self.trait_modifier_resolver)
        self.bloc_simulation_calculator = BlocSimulationCalculator(self.data_manager, self.production_config)
        self.studio_command_service = StudioCommandService(session_factory, self.signals, game_state)
        self.ai_studio_command_service = AIStudioCommandService(session_factory, self.signals, self.data_manager)
        self.revenue_calculator = RevenueCalculator(self.data_manager, self.scene_calc_config)

        # Level 1: Depends on Level 0 services
        self.crew_skill_calculator = CrewSkillCalculator(self.data_manager, self.budget_efficiency_calculator, self.production_config)
        self.tour_interest_calculator = TourInterestCalculator(self.trait_modifier_resolver, self.tour_config, self.data_manager)
        self.market_service = MarketService(market_resolver, self.data_manager.tag_definitions, config=self.market_config)
        self.talent_affinity_calculator = TalentAffinityCalculator(self.scene_calc_config)
        self.availability_checker = TalentAvailabilityChecker(self.data_manager, self.hiring_config)
        self.tour_feasibility_service = TourFeasibilityService(self.data_manager, self.hiring_config)
        self.query_service = GameQueryService(session_factory)
        self.tag_query_service = TagQueryService(self.data_manager)
        self.bloc_cost_calculator = BlocCostCalculator(self.data_manager)
        self.shoot_results_calculator = ShootResultsCalculator(self.data_manager, self.scene_calc_config, self.role_performance_calculator,
            self.stress_calculator
        )
        self.player_settings_service = PlayerSettingsService(session_factory, self.signals)
        self.go_to_list_service = GoToListService(session_factory, self.signals)
        self.email_service = EmailService(session_factory, self.signals)
        self.tag_validation_checker = TagValidationChecker(self.data_manager)
        
        # Level 2: Depends on Level 1 services
        self.ai_studio_director = AIStudioDirector(
            session_factory=session_factory, ai_studio_command_service=self.ai_studio_command_service,
            market_service=self.market_service, data_manager=self.data_manager, revenue_calculator=self.revenue_calculator,
            generator=self.ai_studio_generator
        
        )
        self.contract_command_service = ContractCommandService(session_factory, self.signals, self.query_service, self.contract_config)
        self.talent_demand_calculator = TalentDemandCalculator(
            self.data_manager, self.hiring_config, self.contract_config,
            self.availability_checker, self.role_performance_calculator, self.trait_modifier_resolver
        )
        self.talent_query_service = TalentQueryService(session_factory, self.data_manager, self.query_service, self.talent_location_service,
            self.talent_demand_calculator, self.hiring_config, self.availability_checker, self.shoot_results_calculator,
            self.talent_status_calculator
        )
        self.talent_command_service = TalentCommandService(self.signals, self.scene_calc_config, self.talent_affinity_calculator)
        self.scene_quality_calculator = SceneQualityCalculator(self.data_manager, self.scene_calc_config, self.budget_efficiency_calculator)
        self.post_production_calculator = PostProductionCalculator(self.data_manager)
        self.scene_processing_service = SceneProcessingService(
            self.data_manager, self.talent_command_service, self.scene_calc_config,
            self.tag_validation_checker, self.shoot_results_calculator, self.bloc_simulation_calculator,
            self.scene_quality_calculator, self.post_production_calculator, self.budget_efficiency_calculator
        )
        self.scene_event_trigger_service = SceneEventTriggerService(self.data_manager)
        self.tour_sponsorship_service = TourSponsorshipPreviewService(self.data_manager, self.query_service,
            self.talent_query_service, self.tour_feasibility_service, self.upfront_tour_calculator
        )

        # Level 3: Depends on Level 2 services
        self.casting_command_service = CastingCommandService(session_factory, self.signals, self.query_service,
            self.talent_location_service, self.talent_demand_calculator, self.shoot_results_calculator,
            self.contract_command_service
        )
        self.tour_command_service = TourCommandService(
            session_factory, self.signals, self.casting_command_service, self.query_service,
            self.talent_query_service, self.talent_location_service, self.talent_demand_calculator,
            self.trait_modifier_resolver, self.tour_interest_calculator, self.tour_config
        )
        self.scene_command_service = SceneCommandService(
            session_factory, self.signals, self.data_manager, self.query_service, self.talent_command_service,
            self.market_service, self.email_service, self.scene_processing_service, self.revenue_calculator,
            self.scene_event_trigger_service, self.bloc_cost_calculator, self.crew_skill_calculator
        )
        self.scene_event_command_service = SceneEventCommandService(session_factory, self.data_manager, self.query_service)
        self.time_service = TimeService(
            session_factory, self.signals, self.scene_command_service, self.talent_command_service,
            self.market_service, self.tour_command_service, self.contract_command_service,
            self.ai_studio_director
        )

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
        controller.game_session_service = self.game_session_service
        controller.query_service = self.query_service
        controller.tag_query_service = self.tag_query_service
        controller.tag_validation_checker = self.tag_validation_checker
        controller.talent_command_service = self.talent_command_service
        controller.scene_command_service = self.scene_command_service
        controller.contract_command_service = self.contract_command_service
        controller.casting_command_service = self.casting_command_service
        controller.market_service = self.market_service
        controller.talent_demand_calculator = self.talent_demand_calculator
        controller.tour_command_service = self.tour_command_service
        controller.talent_location_service = self.talent_location_service
        controller.tour_sponsorship_service = self.tour_sponsorship_service
        controller.bloc_cost_calculator = self.bloc_cost_calculator
        controller.shoot_results_calculator = self.shoot_results_calculator
        controller.talent_query_service = self.talent_query_service
        controller.time_service = self.time_service
        controller.go_to_list_service = self.go_to_list_service
        controller.scene_event_command_service = self.scene_event_command_service
        controller.player_settings_service = self.player_settings_service
        controller.email_service = self.email_service
        controller.studio_command_service = self.studio_command_service
    
    def _clear_controller_services(self, controller: 'GameController'):
        """Sets all service references on the controller to None."""
        # Do NOT clear controller.game_session_service here as it persists across sessions
        controller.query_service = None
        controller.tag_query_service = None
        controller.tag_validation_checker = None
        controller.talent_command_service = None
        controller.scene_command_service = None
        controller.contract_command_service = None
        controller.casting_command_service = None
        controller.tour_command_service = None
        controller.tour_sponsorship_service = None
        controller.market_service = None
        controller.talent_demand_calculator = None
        controller.talent_location_service = None
        controller.bloc_cost_calculator = None
        controller.shoot_results_calculator = None
        controller.talent_query_service = None
        controller.time_service = None
        controller.go_to_list_service = None
        controller.scene_event_command_service = None
        controller.player_settings_service = None
        controller.email_service = None
        controller.studio_command_service = None

    def _clear_container_services(self):
        """Sets all service references on this container to None."""
        self.query_service = None
        self.tag_query_service = None
        self.trait_modifier_resolver = None
        self.talent_command_service = None
        self.scene_command_service = None
        self.casting_command_service = None
        self.contract_command_service = None
        self.market_service = None
        self.talent_demand_calculator = None
        self.bloc_cost_calculator
        self.talent_query_service = None
        self.tour_command_service = None
        self.tour_feasibility_service = None
        self.tour_sponsorship_service = None
        self.tour_interest_calculator = None
        self.upfront_tour_calculator = None
        self.talent_status_calculator = None
        self.talent_location_service = None
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
        self.budget_efficiency_calculator = None
        self.stress_calculator = None
        self.crew_skill_calculator = None
        self.bloc_simulation_calculator = None
        self.studio_command_service = None
        self.ai_studio_command_service = None
        self.ai_studio_director = None
        # Do not clear generators or game_session_service

    # --- Builder Factories ---
    
    def create_shooting_bloc_builder(self) -> ShootingBlocBuilder:
        """Factory method to create a ShootingBlocBuilder with injected dependencies."""
        return ShootingBlocBuilder(
            self.data_manager,
            self.production_config,
            self.crew_skill_calculator,
            self.bloc_cost_calculator
        )

    def create_scene_state_editor(self, scene) -> SceneStateEditor:
        """Factory method to create a SceneStateEditor with injected dependencies."""
        return SceneStateEditor(
            scene,
            self.data_manager,
            self.tag_validation_checker
        )

    def _create_configs(self):
        """Creates all configuration dataclasses from the data manager."""
        game_config = self.data_manager.game_config

        self.production_config = ProductionConfig(
            budget_min_penalty_multiplier=game_config.get("budget_min_penalty_multiplier", 0.5),
            budget_overspend_penalty_factor=game_config.get("budget_overspend_penalty_factor", 0.5),
            budget_efficiency_floor=game_config.get("budget_efficiency_floor", 0.1),
            linear_curve_divisor=game_config.get("budget_linear_curve_divisor", 10.0),
            exponential_curve_exponent=game_config.get("budget_exponential_curve_exponent", 2.0),
            step_curve_thresholds={
                0.25: 0.2, 0.5: 0.5, 1.0: 0.8
            }, # Could load from JSON object if needed, using default for now
            crew_skill_baseline_multiplier=game_config.get("crew_skill_baseline_multiplier", 50),
            crew_skill_sigma=game_config.get("crew_skill_sigma", 5),
            bloc_base_momentum=game_config.get("bloc_base_momentum", 50.0),
            bloc_base_stress=game_config.get("bloc_base_stress", 5.0),
            momentum_bonus_threshold=game_config.get("bloc_momentum_bonus_threshold", 75.0),
            momentum_bonus_multiplier=game_config.get("bloc_momentum_bonus_multiplier", 0.8),
            momentum_penalty_threshold=game_config.get("bloc_momentum_penalty_threshold", 25.0),
            momentum_penalty_multiplier=game_config.get("bloc_momentum_penalty_multiplier", 1.2)
        )

        self.market_config = MarketConfig(
            saturation_recovery_rate=game_config.get("market_saturation_recovery_rate", 0.05),
            discovery_interest_threshold=game_config.get("market_discovery_interest_threshold", 1.5),
            discoveries_per_scene=game_config.get("market_discoveries_per_scene", 2)
        )

        self.hiring_config = HiringConfig(
            location_to_location_cost=game_config.get("location_to_location_cost", 100),
            location_to_location_fatigue=game_config.get("location_to_location_fatigue", 5),
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
            minimum_talent_demand=game_config.get("minimum_talent_demand", 100),
            max_scenes_per_week_base=game_config.get("max_scenes_per_week_base", 2),
            max_scenes_per_week_ambition_modifier=game_config.get("max_scenes_per_week_ambition_modifier", 0.1),
            fatigue_refusal_threshold=game_config.get("fatigue_refusal_threshold", 80),
            burnout_penalty_scenes=game_config.get("burnout_penalty_scenes", 1),
            rush_fee_multiplier=game_config.get("hiring_rush_fee_multiplier", 1.25),
            bulk_discount_tiers={int(k): v for k, v in game_config.get("hiring_bulk_discount_tiers", {}).items()},
            hazard_pay_modifiers={int(k): v for k, v in game_config.get("hiring_hazard_pay_modifiers", {}).items()},
            total_budget_refusal_thresholds={int(k): v for k, v in game_config.get("total_budget_refusal_thresholds", {}).items()},
            department_budget_refusal_thresholds={
                k: {int(score): budget for score, budget in v.items()} 
                for k, v in game_config.get("department_budget_refusal_thresholds", {}).items()
            }
        )

        self.contract_config = ContractConfig(
            fallback_salary_multiplier=game_config.get("contract_fallback_salary_multiplier", 5.0),
            preference_salary_floor=game_config.get("contract_preference_salary_floor", 0.1),
            lock_in_premium=game_config.get("contract_lock_in_premium", 1.3),
            initial_compliance=game_config.get("contract_initial_compliance", 100),
            compliance_max=game_config.get("contract_compliance_max", 100),
            compliance_high_pref_threshold=game_config.get("contract_compliance_high_pref_threshold", 1.2),
            compliance_low_pref_threshold=game_config.get("contract_compliance_low_pref_threshold", 0.8),
            compliance_bonus=game_config.get("contract_compliance_bonus", 2),
            compliance_penalty=game_config.get("contract_compliance_penalty", -5),
            disposition_salary_weight=game_config.get("contract_disposition_salary_weight", 0.7),
            skill_salary_weight=game_config.get("contract_skill_salary_weight", 0.3)
        )

        self.tour_config = TourConfig(
            batch_size=game_config.get("tour_batch_size", 4),
            autonomous_fatigue_limit=game_config.get("tour_autonomous_fatigue_limit", 40.0),
            cooldown_weeks=game_config.get("tour_cooldown_weeks", 4),
            location_variety_penalty=game_config.get("tour_location_repeat_penalty", -30),
            base_tour_desire=game_config.get("tour_base_desire", 50.0),
            tour_desire_threshold=game_config.get("tour_desire_threshold", 75.0), 
            workload_desire_modifier=game_config.get("tour_workload_desire_modifier", 10.0),
            min_tour_duration=game_config.get("tour_min_duration", 1),
            max_tour_duration=game_config.get("tour_max_duration", 5)
        )
        
        ds_weights_str_keys = game_config.get("scene_quality_ds_weights", {})
        ds_weights_int_keys = {int(k): v for k, v in ds_weights_str_keys.items()}

        self.scene_calc_config = SceneCalculationConfig(
            stamina_to_pool_multiplier=game_config.get("stamina_to_pool_multiplier", 5),
            in_scene_penalty_scalar=game_config.get("in_scene_penalty_scalar", 0.4),
            fatigue_penalty_scalar=game_config.get("fatigue_penalty_scalar", 0.3),
            fatigue_passive_decay_rate=game_config.get("fatigue_passive_decay_rate", 5),
            fatigue_active_recovery_bonus=game_config.get("fatigue_active_recovery_bonus", 20),
            fatigue_stamina_recovery_modifier=game_config.get("fatigue_stamina_recovery_modifier", 0.5),
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
            popularity_gain_scalar=game_config.get("popularity_gain_scalar", 0.05),
            base_acting_stress=game_config.get("stress_base_acting", 0.5),
            multitasking_stress_multiplier=game_config.get("stress_multitasking_multiplier", 0.5),
            craft_services_stress_relief_scalar=game_config.get("stress_craft_services_relief_scalar", 0.05),
            max_stress_threshold=game_config.get("stress_max_threshold", 100.0),
            burnout_conversion_rate=game_config.get("stress_burnout_conversion_rate", 1.0)
        )