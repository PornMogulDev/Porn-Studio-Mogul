import logging
from typing import Dict
from sqlalchemy.orm import selectinload, Session
from sqlalchemy.orm.attributes import flag_modified

from data.game_state import Scene, Talent, ShootingBloc
from data.data_manager import DataManager
from database.db_models import (SceneDB, TalentDB, StudioStateDB, ShootingBlocDB, 
                                ScenePerformerContributionDB, TalentChemistryDB)
from services.command.talent_command_service import TalentCommandService
from services.models.configs import SceneCalculationConfig
from services.models.results import ShootCalculationResult
from services.calculation.tag_validation_checker import TagValidationChecker
from services.calculation.shoot_results_calculator import ShootResultsCalculator
from services.calculation.scene_quality_calculator import SceneQualityCalculator
from services.calculation.post_production_calculator import PostProductionCalculator
from services.calculation.budget_efficiency_calculator import BudgetEfficiencyCalculator
from services.calculation.bloc_simulation_calculator import BlocSimulationCalculator

logger = logging.getLogger(__name__)

class SceneProcessingService:
    """
    A service responsible for processing scenes through different stages like
    shooting and post-production. It orchestrates pure calculators and applies
    their results to the database within a transaction managed by a caller service.
    """
    def __init__(self, data_manager: DataManager, talent_command_service: TalentCommandService,
                 config: SceneCalculationConfig, tag_validation_checker: TagValidationChecker,
                 shoot_results_calc: ShootResultsCalculator, bloc_sim_calc: BlocSimulationCalculator,
                 scene_quality_calc: SceneQualityCalculator, post_prod_calc: PostProductionCalculator,
                 budget_efficiency_calculator: BudgetEfficiencyCalculator):
        self.data_manager = data_manager
        self.talent_command_service = talent_command_service
        self.config = config
        self.tag_validation_checker = tag_validation_checker
        self.shoot_results_calculator = shoot_results_calc
        self.bloc_simulation_calculator = bloc_sim_calc
        self.scene_quality_calculator = scene_quality_calc
        self.post_production_calculator = post_prod_calc
        self.budget_efficiency_calculator = budget_efficiency_calculator

    def prepare_for_shoot_calculation(self, session: Session, scene_db: SceneDB):
        """
        Handles preparatory database writes before the main calculation phase.
        This includes deducting costs and discovering chemistry.
        """
        # Deduct salary costs
        total_salary_cost = sum(c.salary for c in scene_db.cast)
        if total_salary_cost > 0:
            studio_state = session.query(StudioStateDB).get(1)
            studio_state.money = studio_state.money - total_salary_cost

        # Discover and create chemistry between cast members
        talent_ids = [c.talent_id for c in scene_db.cast]
        talents_db = session.query(TalentDB).options(
            selectinload(TalentDB.chemistry_a).joinedload(TalentChemistryDB.talent_b),
            selectinload(TalentDB.chemistry_b).joinedload(TalentChemistryDB.talent_a)
        ).filter(TalentDB.id.in_(talent_ids)).all()
        cast_talents_dc = [t.to_dataclass(Talent) for t in talents_db]
        
        self.talent_command_service.discover_and_create_chemistry(session, cast_talents_dc)

    def run_shoot_calculations(self, session: Session, scene_db: SceneDB, shoot_modifiers: Dict) -> ShootCalculationResult:
        """
        Fetches data, orchestrates pure calculators, and returns a consolidated DTO.
        This method performs NO database writes.
        """
        # --- 1. DATA FETCHING ---
        scene = scene_db.to_dataclass(Scene)
        talent_ids = list(scene.final_cast.values())
        talents_db = session.query(TalentDB).options(
            selectinload(TalentDB.popularity_scores)
        ).filter(TalentDB.id.in_(talent_ids)).all()
        cast_talents_dc = [t.to_dataclass(Talent) for t in talents_db]

        bloc_db = session.query(ShootingBlocDB).get(scene.bloc_id) if scene.bloc_id else None
        bloc_dc = bloc_db.to_dataclass(ShootingBloc) if bloc_db else None

        # --- 2. PREPARE CONTEXT ---
        bloc_context = {}
        if bloc_db:
            # Look up pre-rolled scores from the cache
            # Fallback to 50 (Average) if missing
            cs_score = bloc_db.production_cache.get('craft_services', 50)
            hs_score = bloc_db.production_cache.get('health_safety', 50)
            
            # Normalize scores (0-100) to efficiency scalars (approx 1.0 baseline)
            # Used by StressCalculator
            cs_efficiency = cs_score / 50.0
            
            bloc_context = {
                'location_def': self.data_manager.production_locations.get(bloc_db.set_location_id, {}),
                'craft_services_efficiency': cs_efficiency,
                'health_safety_score': hs_score,
                'crew_assignments': bloc_db.crew_assignments,
                'department_budgets': bloc_db.department_budgets,
                'production_cache': bloc_db.production_cache, # <--- New: Pass the cache
                'visual_style_id': bloc_db.visual_style_id
            }

        # Add current momentum to context for calculations
        if bloc_db:
             bloc_context['current_momentum'] = bloc_db.current_momentum

        studio_state = session.query(StudioStateDB).get(1)
        active_policies = studio_state.active_policies if studio_state and studio_state.active_policies else []
        
        # --- 3. DELEGATE TO PURE CALCULATORS ---
        # 3a. Calculate Talent Outcomes
        talent_outcomes = self.shoot_results_calculator.calculate_talent_outcomes(
            scene, cast_talents_dc, active_policies, bloc_context
        )
        
        # 3b. Calculate Bloc Simulation (Momentum/Stress)
        momentum_delta, stress_delta = 0.0, 0.0
        if bloc_dc:
            momentum_delta, stress_delta = self.bloc_simulation_calculator.calculate_simulation_deltas(
                bloc_dc
            )
        
        scene.performer_stamina_costs = {str(o.talent_id): o.stamina_cost for o in talent_outcomes}

        existing_tags = set(scene.global_tags) | set(scene.assigned_tags.keys())
        discovered_tags = self.tag_validation_checker.analyze_cast(cast_talents_dc, existing_tags)
        scene.auto_tags = discovered_tags

        quality_result = self.scene_quality_calculator.calculate_quality(
            scene, cast_talents_dc, shoot_modifiers, bloc_context
        )

        # --- 4. PACKAGE AND RETURN DTO ---
        return ShootCalculationResult(
            talent_outcomes=talent_outcomes,
            quality_result=quality_result,
            discovered_tags=discovered_tags,
            momentum_delta=momentum_delta,
            stress_delta=stress_delta
        )

    def apply_shoot_calculation_results(self, session: Session, scene_db: SceneDB, result: ShootCalculationResult):
        """
        Applies the data from a ShootCalculationResult DTO to the database models.
        """
        # Update Bloc Simulation State
        if scene_db.bloc_id:
            bloc_db = session.query(ShootingBlocDB).get(scene_db.bloc_id)
            if bloc_db:
                # Clamp values
                new_momentum = max(0.0, min(100.0, bloc_db.current_momentum + result.momentum_delta))
                new_stress = max(0.0, bloc_db.current_stress + result.stress_delta)
                
                bloc_db.current_momentum = new_momentum
                bloc_db.current_stress = new_stress

        talent_ids = [outcome.talent_id for outcome in result.talent_outcomes]
        talents_db = session.query(TalentDB).filter(TalentDB.id.in_(talent_ids)).all()
        talent_db_map = {t.id: t for t in talents_db}

        for outcome in result.talent_outcomes:
            talent_db = talent_db_map.get(outcome.talent_id)
            if not talent_db: continue
            
            if outcome.fatigue_result:
                talent_db.fatigue = outcome.fatigue_result.new_fatigue_level

                talent_db.stress += outcome.stress_gain
            
            for skill, gain in outcome.skill_gains.items():
                current_val = getattr(talent_db, skill)
                setattr(talent_db, skill, min(self.config.maximum_skill_level, current_val + gain))
            
            talent_db.experience = min(100.0, talent_db.experience + outcome.experience_gain)

        scene_db.performer_contributions_rel.clear()
        for contrib_data in result.quality_result.performer_contributions:
            contrib_db = ScenePerformerContributionDB(
                scene_id=scene_db.id,
                talent_id=contrib_data['talent_id'],
                contribution_key=contrib_data['contribution_key'],
                quality_score=contrib_data['quality_score']
            )
            scene_db.performer_contributions_rel.append(contrib_db)
        
        # Re-fetch stamina costs from the talent outcomes in the result DTO
        stamina_costs = {str(o.talent_id): o.stamina_cost for o in result.talent_outcomes}
        scene_db.performer_stamina_costs = stamina_costs
        
        scene_db.auto_tags = result.discovered_tags.copy()
        scene_db.tag_qualities = result.quality_result.tag_qualities
        scene_db.status = 'shot'
        scene_db.weeks_remaining = 0

    def apply_post_production_effects(self, session: Session, scene_db: SceneDB):
        """
        Calculates and applies quality modifiers from post-production choices
        and finalizes the scene for release.
        """
        bloc_db = session.query(ShootingBlocDB).get(scene_db.bloc_id) if scene_db.bloc_id else None

        current_contributions = [
            {'talent_id': c.talent_id, 'contribution_key': c.contribution_key, 'quality_score': c.quality_score}
            for c in scene_db.performer_contributions_rel
        ]

        camera_count = bloc_db.camera_count if bloc_db else 1

        post_prod_result = self.post_production_calculator.apply_effects(
            current_tag_qualities=scene_db.tag_qualities or {},
            current_contributions=current_contributions,
            post_prod_choices=scene_db.post_production_choices or {},
            camera_count=camera_count,
        )

        if post_prod_result:
            scene_db.tag_qualities = post_prod_result.new_tag_qualities
            flag_modified(scene_db, "tag_qualities")

            new_scores_map = {(c['talent_id'], c['contribution_key']): c['quality_score'] for c in post_prod_result.new_performer_contributions}
            for contrib_db in scene_db.performer_contributions_rel:
                new_score = new_scores_map.get((contrib_db.talent_id, contrib_db.contribution_key))
                if new_score is not None:
                    contrib_db.quality_score = new_score

            mod_details = scene_db.revenue_modifier_details.copy() if scene_db.revenue_modifier_details else {}
            mod_details.update(post_prod_result.revenue_modifier_details)
            scene_db.revenue_modifier_details = mod_details
            flag_modified(scene_db, "revenue_modifier_details")

        scene_db.status = 'ready_to_release'