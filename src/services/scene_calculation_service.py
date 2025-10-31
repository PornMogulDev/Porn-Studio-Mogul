import logging
from typing import Dict
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import selectinload

from data.game_state import Scene, Talent
from data.data_manager import DataManager
from database.db_models import ( SceneDB, MarketGroupStateDB, TalentDB, GameInfoDB, ShootingBlocDB,
                                ScenePerformerContributionDB, SceneCastDB, TalentChemistryDB )
from services.talent_service import TalentService
from services.market_service import MarketService
from services.service_config import SceneCalculationConfig
from services.auto_tag_analyzer import AutoTagAnalyzer
from services.shoot_results_calculator import ShootResultsCalculator
from services.scene_quality_calculator import SceneQualityCalculator
from services.post_production_calculator import PostProductionCalculator

logger = logging.getLogger(__name__)

class SceneCalculationService:
    def __init__(self, db_session, data_manager: DataManager, talent_service: TalentService, market_service: MarketService, config: SceneCalculationConfig, auto_tag_analyzer: AutoTagAnalyzer,
                 shoot_results_calc: ShootResultsCalculator, scene_quality_calc: SceneQualityCalculator, post_prod_calc: PostProductionCalculator):
        self.session = db_session
        self.data_manager = data_manager
        self.talent_service = talent_service
        self.market_service = market_service
        self.config = config
        self.auto_tag_analyzer = auto_tag_analyzer
        self.shoot_results_calculator = shoot_results_calc
        self.scene_quality_calculator = scene_quality_calc
        self.post_production_calculator = post_prod_calc
    
    def calculate_shoot_results(self, scene_db: SceneDB, shoot_modifiers: Dict):
        # --- 1. PRE-CALCULATION & DATA FETCHING ---

        # Deduct salary costs
        total_salary_cost = sum(c.salary for c in scene_db.cast)
        
        if total_salary_cost > 0:
            money_info = self.session.query(GameInfoDB).filter_by(key='money').one()
            money_info.value = str(int(float(money_info.value)) - total_salary_cost)

        scene = scene_db.to_dataclass(Scene) 
        talent_ids = list(scene.final_cast.values())
        talents_db = self.session.query(TalentDB).filter(TalentDB.id.in_(talent_ids)).all()
        cast_talents_dc = [t.to_dataclass(Talent) for t in talents_db]

        week_info = self.session.query(GameInfoDB).filter_by(key='week').one()
        year_info = self.session.query(GameInfoDB).filter_by(key='year').one()
        current_week, current_year = int(week_info.value), int(year_info.value)

        # --- 2. DELEGATE TO PURE CALCULATORS ---

        # Discover chemistry and auto-tags
        cast_talents_by_id = {t.id: t for t in cast_talents_dc}
        self.talent_service.discover_and_create_chemistry(cast_talents_dc)

        # Calculate talent outcomes (stamina, fatigue, skills)
        talent_outcomes = self.shoot_results_calculator.calculate_talent_outcomes(
            scene, cast_talents_dc, current_week, current_year
        )

        # Update scene dataclass with stamina costs for quality calculation
        scene.performer_stamina_costs = {str(o.talent_id): o.stamina_cost for o in talent_outcomes}

        # Discover auto tags
        existing_tags = set(scene.global_tags) | set(scene.assigned_tags.keys())
        discovered_tags = self.auto_tag_analyzer.analyze_cast(cast_talents_dc, existing_tags)
        scene.auto_tags = discovered_tags # Update scene dataclass for quality calculation

        # Calculate scene quality
        bloc_db = self.session.query(ShootingBlocDB).get(scene.bloc_id) if scene.bloc_id else None
        quality_result = self.scene_quality_calculator.calculate_quality(
            scene, cast_talents_dc, shoot_modifiers, bloc_db.production_settings if bloc_db else None
        )

        # --- 3. APPLY RESULTS TO DATABASE MODELS ---

        # Apply talent outcomes
        talent_db_map = {t.id: t for t in talents_db}
        for outcome in talent_outcomes:
            talent_db = talent_db_map.get(outcome.talent_id)
            if not talent_db: continue
            
            if outcome.fatigue_result:
                talent_db.fatigue = outcome.fatigue_result.new_fatigue_level
                talent_db.fatigue_end_week = outcome.fatigue_result.fatigue_end_week
                talent_db.fatigue_end_year = outcome.fatigue_result.fatigue_end_year
            
            for skill, gain in outcome.skill_gains.items():
                current_val = getattr(talent_db, skill)
                setattr(talent_db, skill, min(self.config.maximum_skill_level, current_val + gain))
            
            talent_db.experience = min(100.0, talent_db.experience + outcome.experience_gain)

        # Apply scene quality results
        scene_db.performer_contributions_rel.clear()
        for contrib_data in quality_result.performer_contributions:
            contrib_db = ScenePerformerContributionDB(
                scene_id=scene_db.id,
                talent_id=contrib_data['talent_id'],
                contribution_key=contrib_data['contribution_key'],
                quality_score=contrib_data['quality_score']
            )
            scene_db.performer_contributions_rel.append(contrib_db)
        
        scene_db.performer_stamina_costs = scene.performer_stamina_costs.copy()
        scene_db.auto_tags = scene.auto_tags.copy()
        scene_db.tag_qualities = quality_result.tag_qualities

        scene_db.status = 'shot'
        scene_db.weeks_remaining = 0

    def apply_post_production_effects(self, scene_db: SceneDB):
        """
        Calculates and applies quality modifiers from post-production choices
        and finalizes the scene for release.
        """
        bloc_db = self.session.query(ShootingBlocDB).get(scene_db.bloc_id) if scene_db.bloc_id else None

        # We need contributions as a list of dicts for the pure calculator
        current_contributions = [
            {'talent_id': c.talent_id, 'contribution_key': c.contribution_key, 'quality_score': c.quality_score}
            for c in scene_db.performer_contributions_rel
        ]

        post_prod_result = self.post_production_calculator.apply_effects(
            current_tag_qualities=scene_db.tag_qualities or {},
            current_contributions=current_contributions,
            post_prod_choices=scene_db.post_production_choices or {},
            bloc_production_settings=(bloc_db.production_settings if bloc_db else {}),
            default_camera_tier=self.data_manager.game_config.get("default_camera_setup_tier", "1")
        )

        if post_prod_result:
            scene_db.tag_qualities = post_prod_result.new_tag_qualities
            flag_modified(scene_db, "tag_qualities")

            # Re-sync DB contributions with the new scores
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