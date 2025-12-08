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
        """Finds scenes releasing this week and applies saturation to the market."""
        releasing_scenes = self.command_service.get_scenes_releasing_this_week(session, current_week)
        
        saturation_updates = {}
        
        for scene in releasing_scenes:
            # Apply saturation updates stored in the scene data
            # The revenue calculator logic stores this in 'market_saturation_updates' result
            # which we should ideally have stored, but for now we can infer or 
            # assume the AI scene creates a fixed amount of saturation per interest.
            # Alternatively, if we updated AISceneDB to store saturation cost, we'd use that.
            # For now, we will assume the viewer_group_interest is the key.
            pass # To be fully implemented once AISceneDB stores saturation specific details
            # Re-implementing simplified saturation hit for now based on interest:
            for group, interest in scene.viewer_group_interest.items():
                 if interest > 0:
                     # Approximate saturation hit
                     cost = interest * 0.15 # Using default constant
                     if group in saturation_updates:
                         saturation_updates[group] += cost
                     else:
                         saturation_updates[group] = cost

            logger.info(f"AI RELEASE: {scene.title} (Rev: ${scene.revenue:,}) released.")

        # Apply to MarketService
        if saturation_updates:
            self.market_service.update_saturation_from_release(session, saturation_updates)

    def _create_scene(self, session: Session, studio: AIStudioDB, current_week: int):
        """Generates scene data and persists it."""
        
        # 1. Generate Name: "{StudioName} #{Count}"
        # Note: We query count live, so multiple scenes in one batch get sequential numbers
        prev_count = self.command_service.get_studio_scene_count(session, studio.id)
        new_count = prev_count + 1
        title = f"{studio.name} #{new_count}"

        # 2. Generate Params via Archetype
        params = self.generator.generate_scene_parameters(studio.archetype_id, current_week)
        if not params:
            logger.warning(f"Could not generate params for studio {studio.id} (Archetype: {studio.archetype_id})")
            return

        # 3. Build Revenue Input DTO directly from params
        global_tags = []
        content_tags = []
        tag_qualities = params.get('tags', {})

        # Determine default runtime for AI scenes (could be parametrized later)
        runtime = 20 

        # Fetch weights from config to match player economy
        action_base_weight = self.data_manager.game_config.get("revenue_weight_default_action_appeal", 10.0)
        physical_weight = self.data_manager.game_config.get("revenue_weight_focused_physical_tag", 5.0)
        
        for tag_name, quality in tag_qualities.items():
            tag_def = self.data_manager.tag_definitions.get(tag_name)
            if not tag_def: continue
            
            t_type = tag_def.get('type')
            if t_type == 'Thematic':
                global_tags.append(tag_name)
            elif t_type == 'Physical':
                content_tags.append(ContentTagInput(
                    tag_name=tag_name,
                    tag_type=t_type,
                    quality=quality / 100.0,
                    weight=physical_weight,
                    orientation=params.get('orientation'),
                    concept=tag_def.get('concept')
                ))
            elif t_type == 'Action':
                # For AI, we assume Action tags split the runtime evenly.
                # Since we don't know the exact count ahead of time in this loop, 
                # we'll approximate based on the Generator's behavior (usually ~2 action tags).
                # A safer bet for general scaling is to assume 50% runtime focus per tag if there are 2.
                # So we weight them as action_base_weight * 0.5
                content_tags.append(ContentTagInput(
                    tag_name=tag_name,
                    tag_type=t_type,
                    quality=quality / 100.0,
                    weight=action_base_weight * 0.5, 
                    orientation=params.get('orientation'), # Assume tag matches scene orientation
                    concept=tag_def.get('concept')
                ))

        revenue_input = RevenueInput(
            title=title,
            focus_target=params.get('target_market', 'Straight Men'),
            dom_sub_level=params.get('dom_sub_level', 0),
            global_tags=global_tags,
            total_runtime_minutes=runtime,
            content_tags=content_tags,
            star_power_scores={} # AI scenes have no star power for now
        )
                
        # 4. Calculate Revenue
        market_states_db = session.query(MarketGroupStateDB).all()
        market_states = {m.name: MarketGroupState(name=m.name, current_saturation=m.current_saturation) for m in market_states_db}
        resolved_groups = self.market_service.get_all_resolved_group_data()
        
        result = self.revenue_calculator.calculate_revenue(revenue_input, market_states, resolved_groups)
        
        # 5. Prepare Params for persistence (needs simple lists/dicts)
        # We reconstruct the params dict to match what AIStudioCommandService expects for JSON storage
        persistence_params = params.copy()
        persistence_params['global_tags'] = global_tags
        persistence_params['assigned_tags'] = tag_qualities 
        persistence_params['action_segments'] = [t.tag_name for t in content_tags if t.tag_type == 'Action']

        self.command_service.create_ai_scene(
            session=session,
            studio_id=studio.id,
            title=title,
            current_week=current_week,
            params=persistence_params,
            revenue_result=result
        )