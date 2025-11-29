import logging
import random
from sqlalchemy.orm import Session

from services.command.ai_studio_command_service import AIStudioCommandService
from services.market_service import MarketService
from data.data_manager import DataManager
from database.db_models import AIStudioDB

logger = logging.getLogger(__name__)

class AIStudioDirector:
    """
    Controls the behavior of AI Studios. Determines when they create scenes,
    generates scene parameters, and handles the release process.
    """
    def __init__(self, session_factory, ai_studio_command_service: AIStudioCommandService,
                 market_service: MarketService, data_manager: DataManager):
        self.session_factory = session_factory
        self.command_service = ai_studio_command_service
        self.market_service = market_service
        self.data_manager = data_manager

    def process_weekly_ai_decisions(self, session: Session, current_absolute_week: int):
        """
        Main entry point called by TimeService every week.
        1. Checks for releases and applies market impact.
        2. Iterates studios to make production decisions.
        """
        # 1. Handle Releases (Scenes finishing production)
        self._process_scene_releases(session, current_absolute_week)

        # 2. Handle Production (Deciding to make new scenes)
        active_studios = session.query(AIStudioDB).filter_by(active=True).all()
        
        for studio in active_studios:
            if self._should_create_scene(studio, current_absolute_week):
                self._create_scene(session, studio, current_absolute_week)

    def _process_scene_releases(self, session: Session, current_week: int):
        """Finds scenes releasing this week and applies saturation to the market."""
        releasing_scenes = self.command_service.get_scenes_releasing_this_week(session, current_week)
        
        saturation_updates = {}
        
        for scene in releasing_scenes:
            # Calculate saturation impact based on quality
            # Logic: A 100 quality movie hits saturation harder than a 50 quality one.
            # Base scalar determines how much "damage" an AI movie does.
            # 0.05 means a perfect AI movie fills 5% of the market demand.
            base_impact = 0.05 
            impact = (scene.quality_score / 100.0) * base_impact
            
            # Aggregate updates per market group
            if scene.target_market_group in saturation_updates:
                saturation_updates[scene.target_market_group] += impact
            else:
                saturation_updates[scene.target_market_group] = impact

            logger.info(f"AI RELEASE: {scene.title} hitting {scene.target_market_group} for {impact:.3f} saturation.")

        # Apply to MarketService
        if saturation_updates:
            self.market_service.update_saturation_from_release(session, saturation_updates)

    def _should_create_scene(self, studio: AIStudioDB, current_week: int) -> bool:
        """
        Simple RNG logic to determine if a studio starts a project.
        Based on scenes_per_month_target.
        """
        # E.g., target 4 per month = 1 per week avg.
        # Chance = target / 4.0 weeks.
        chance = studio.scenes_per_month_target / 4.0
        
        # Add random noise so they don't all shoot on the same weeks
        roll = random.random()
        return roll < chance

    def _create_scene(self, session: Session, studio: AIStudioDB, current_week: int):
        """Generates scene data and persists it."""
        
        # 1. Generate Name: "{StudioName} #{Count}"
        prev_count = self.command_service.get_studio_scene_count(session, studio.id)
        new_count = prev_count + 1
        title = f"{studio.name} #{new_count}"

        # 2. Pick Target Market
        # Prefer their specialized groups, or random if none set
        if studio.preferred_market_groups:
            target_market = random.choice(studio.preferred_market_groups)
        else:
            # Fallback to any valid market group from data
            groups = [g['name'] for g in self.data_manager.market_data.get('viewer_groups', [])]
            target_market = random.choice(groups) if groups else "General"

        # 3. Generate Quality
        # Prototype: Random between 40 (Mediocre) and 85 (Great)
        quality = random.uniform(40.0, 85.0)

        # 4. Persist
        self.command_service.create_ai_scene(
            session=session,
            studio_id=studio.id,
            title=title,
            current_week=current_week,
            target_market=target_market,
            quality=quality
        )