import logging
from typing import Tuple
from sqlalchemy.orm import selectinload

from database.db_models import GameInfoDB, SceneDB, TalentDB, Talent
from services.command.talent_command_service import TalentCommandService
from services.scene_service import SceneService
from services.market_service import MarketService
from services.models.results import WeekAdvancementResult

logger = logging.getLogger(__name__)

class TimeService:
    def __init__(self, db_session, signals, scene_service: SceneService, 
                 talent_command_service: TalentCommandService, market_service: MarketService):
        self.session = db_session
        self.signals = signals
        self.scene_service = scene_service
        self.talent_command_service = talent_command_service
        self.market_service = market_service

    def _get_current_time(self) -> Tuple[int, int]:
        """Reads the current time directly from the database."""
        week_info = self.session.query(GameInfoDB).filter_by(key='week').one()
        year_info = self.session.query(GameInfoDB).filter_by(key='year').one()
        return int(week_info.value), int(year_info.value)

    def advance_week(self) -> WeekAdvancementResult:
        """Orchestrates all weekly game state changes within a single transaction."""
        current_week, current_year = self._get_current_time()
        current_date_val = current_year * 52 + current_week
        
        try:
            # --- 1. Perform all weekly updates ---
            market_changed = self.market_service.recover_all_market_saturation()
            
            # Shoot scheduled scenes
            scenes_to_shoot = self.session.query(SceneDB).filter_by(
                status='scheduled',
                scheduled_week=current_week,
                scheduled_year=current_year
            ).all()
            
            scenes_shot_count = 0
            for scene_db in scenes_to_shoot:
                event_occurred = self.scene_service.shoot_scene(scene_db)
                scenes_shot_count += 1
                if event_occurred:
                    # An event paused execution. Commit what we have and stop.
                    self.session.commit()
                    return WeekAdvancementResult(
                        new_week=current_week, new_year=current_year,
                        was_paused=True, scenes_shot=scenes_shot_count,
                        market_changed=market_changed
                    )

            # Update post-production and advance time
            edited_scenes = self.scene_service.process_weekly_post_production()

            next_week, next_year = (current_week + 1, current_year)
            is_new_year = False
            if next_week > 52:
                    next_week = 1
                    next_year += 1
                    is_new_year = True

            talent_pool_changed = self.talent_command_service.process_weekly_updates(current_date_val, is_new_year)

            # --- 2. Persist the new time ---
            week_info = self.session.query(GameInfoDB).filter_by(key='week').one()
            year_info = self.session.query(GameInfoDB).filter_by(key='year').one()
            week_info.value, year_info.value = str(next_week), str(next_year)
            
            # --- 3. Commit and return result ---
            self.session.commit()
            return WeekAdvancementResult(
                new_week=next_week, new_year=next_year,
                scenes_shot=scenes_shot_count, scenes_edited=len(edited_scenes),
                market_changed=market_changed, talent_pool_changed=talent_pool_changed
            )
        except Exception as e:
            logger.error(f"Error during week advancement: {e}", exc_info=True)
            self.session.rollback()
            # Return current state on failure
            return WeekAdvancementResult(new_week=current_week, new_year=current_year, was_paused=True)