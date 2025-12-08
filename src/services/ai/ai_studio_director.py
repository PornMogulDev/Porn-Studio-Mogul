import logging
import random
from typing import Optional
from sqlalchemy.orm import Session

from data.data_manager import DataManager
from data.game_state import Scene, ActionSegment, MarketGroupState
from database.db_models import AIStudioDB, MarketGroupStateDB
from services.command.ai_studio_command_service import AIStudioCommandService
from services.calculation.revenue_calculator import RevenueCalculator
from services.market_service import MarketService
from core.ai_studio_generator import AIStudioGenerator
from services.models.inputs import RevenueInput, ContentTagInput

logger = logging.getLogger(__name__)

class AIStudioDirector:
    """
    Controls the behavior of AI Studios. Determines when they create scenes,
    generates scene parameters, and handles the release process.
    """
    def __init__(self, session_factory, ai_studio_command_service: AIStudioCommandService, 
                 market_service: MarketService, data_manager: DataManager,
                 revenue_calculator: RevenueCalculator, generator: AIStudioGenerator):
        self.session_factory = session_factory
        self.command_service = ai_studio_command_service
        self.market_service = market_service
        self.data_manager = data_manager
        self.revenue_calculator = revenue_calculator
        self.generator = generator

    def process_weekly_ai_decisions(self, session: Session, current_absolute_week: int):
        """
        Main entry point called by TimeService every week.
        1. Checks for releases and applies market impact.
        2. Iterates studios to make production decisions.
        """
        from utils import time_utils
        
        # 1. Handle Releases (Scenes finishing production)
        self._process_scene_releases(session, current_absolute_week)

        # 2. Handle Production (Deciding to make new scenes)
        # Monthly batching: Logic runs only on the first week of the month.
        _, _, week_in_month = time_utils.to_month(current_absolute_week)
        
        if week_in_month == 1:
            active_studios = session.query(AIStudioDB).filter_by(active=True).all()
            
            for studio in active_studios:
                # Distribute the monthly target across the 4 weeks of this month
                target_count = studio.scenes_per_month_target
                
                # Simple randomization to not have exact number every month
                actual_count = int(random.gauss(target_count, 1.0))
                actual_count = max(0, actual_count)
                
                for _ in range(actual_count):
                    # Randomly assign to one of the 4 weeks in this month
                    week_offset = random.randint(0, 3)
                    creation_week = current_absolute_week + week_offset
                    
                    self._create_scene(session, studio, creation_week)

    def _process_scene_releases(self, session: Session, current_week: int):
        """
        Finds scenes releasing this week, calculates their revenue and market
        impact based on the current market state, and applies saturation.
        """
        releasing_scenes = self.command_service.get_scenes_releasing_this_week(session, current_week)
        if not releasing_scenes:
            return

        aggregated_saturation_updates = {}
        market_states_db = session.query(MarketGroupStateDB).all()
        market_states = {m.name: MarketGroupState(name=m.name, current_saturation=m.current_saturation) for m in market_states_db}
        resolved_groups = self.market_service.get_all_resolved_group_data()

        for scene in releasing_scenes:
            params = scene.scene_parameters
            
            # 1. Rebuild the RevenueInput DTO from stored parameters
            revenue_input = self.generator.create_revenue_input_from_params(
                title=scene.title,
                params=params,
                data_manager=self.data_manager
            )

            # 2. Calculate revenue against the CURRENT market state
            result = self.revenue_calculator.calculate_revenue(revenue_input, market_states, resolved_groups)
            
            # 3. Log the outcome and update the scene's revenue for records
            scene.revenue = result.total_revenue
            logger.info(f"AI RELEASE: {scene.title} (Rev: ${scene.revenue:,}) released.")

            # 4. Aggregate saturation costs
            for group, cost in result.market_saturation_updates.items():
                aggregated_saturation_updates[group] = aggregated_saturation_updates.get(group, 0.0) + cost
        
        # 5. Apply all aggregated updates to the market in one go
        if aggregated_saturation_updates:
            self.market_service.update_saturation_from_release(session, aggregated_saturation_updates)

    def _create_scene(self, session: Session, studio: AIStudioDB, current_week: int):
        """Generates scene parameters and persists them."""
        
        # 1. Generate Name
        prev_count = self.command_service.get_studio_scene_count(session, studio.id)
        new_count = prev_count + 1
        title = f"{studio.name} #{new_count}"

        # 2. Generate scene parameters from the studio's archetype
        params = self.generator.generate_scene_parameters(studio.archetype_id, current_week)
        if not params:
            logger.warning(f"Could not generate params for studio {studio.id} (Archetype: {studio.archetype_id})")
            return

        # 3. Persist the generated parameters for a future release date
        self.command_service.create_ai_scene(
            session=session,
            studio_id=studio.id,
            title=title,
            current_week=current_week,
            params=params
        )