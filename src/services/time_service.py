import logging
from typing import Tuple
from sqlalchemy.orm import selectinload, Session

from database.db_models import GameInfoDB, SceneDB, TalentDB, Talent
from services.command.scene_command_service import SceneCommandService
from services.command.talent_command_service import TalentCommandService
from services.market_service import MarketService
from services.models.results import WeekAdvancementResult

logger = logging.getLogger(__name__)

class TimeService:
    def __init__(self, session_factory, signals, scene_command_service: SceneCommandService, 
                 talent_command_service: TalentCommandService, market_service: MarketService):
        self.session_factory = session_factory
        self.signals = signals
        self.scene_command_service = scene_command_service
        self.talent_command_service = talent_command_service
        self.market_service = market_service

    def _get_current_time(self, session: Session) -> Tuple[int, int]:
        """Reads the current time directly from the database."""
        week_info = session.query(GameInfoDB).filter_by(key='week').one()
        year_info = session.query(GameInfoDB).filter_by(key='year').one()
        return int(week_info.value), int(year_info.value)

    def advance_week(self) -> WeekAdvancementResult:
        """Orchestrates all weekly game state changes within a single transaction."""
        session = self.session_factory()
        try:
            current_week, current_year = self._get_current_time(session)
            current_date_val = current_year * 52 + current_week
            money_info = session.query(GameInfoDB).filter_by(key='money').one()
        
            # --- 1. Perform all weekly updates ---
            market_changed = self.market_service.recover_all_market_saturation(session)
            
            # Shoot scheduled scenes
            scenes_to_shoot = session.query(SceneDB).filter_by(
                status='scheduled',
                scheduled_week=current_week,
                scheduled_year=current_year
            ).all()

            # Keep track of who has worked this week for the fatigue decay rate
            talents_who_worked_ids = set()
            
            scenes_shot_count = 0
            for scene_db in scenes_to_shoot:
                event_occurred = self.scene_command_service.shoot_scene(session, scene_db)
                scenes_shot_count += 1
                if event_occurred:
                    # An event paused execution. Commit what we have and stop.
                    session.commit()
                    return WeekAdvancementResult(
                        new_week=current_week, new_year=current_year,
                        new_money=int(float(money_info.value)),
                        was_paused=True, scenes_shot=scenes_shot_count,
                        market_changed=market_changed
                    )
                # Update the working talent list
                for cast_member in scene_db.cast:
                    talents_who_worked_ids.add(cast_member.talent_id)

            # Update post-production and advance time
            edited_scenes = self.scene_command_service.process_weekly_post_production(session)

            next_week, next_year = (current_week + 1, current_year)
            is_new_year = False
            if next_week > 52:
                    next_week = 1
                    next_year += 1
                    is_new_year = True

            talent_pool_changed = self.talent_command_service.process_weekly_updates(session, is_new_year, talents_who_worked_ids)

            # --- 2. Persist the new time ---
            week_info = session.query(GameInfoDB).filter_by(key='week').one()
            year_info = session.query(GameInfoDB).filter_by(key='year').one()
            
            week_info.value = str(next_week)
            year_info.value = str(next_year)
            
            # --- 3. Commit and return result ---
            session.commit()
            return WeekAdvancementResult(
            new_week=next_week, new_year=next_year,
            new_money=int(float(money_info.value)),
            scenes_shot=scenes_shot_count, scenes_edited=len(edited_scenes),
            market_changed=market_changed, talent_pool_changed=talent_pool_changed
        )
        except Exception as e:
            logger.error(f"Error during week advancement: {e}", exc_info=True)
            session.rollback()
            # Return current state on failure
            return WeekAdvancementResult(new_week=current_week, new_year=current_year, new_money=int(float(money_info.value)), was_paused=True)
        finally:
            session.close()