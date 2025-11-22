import logging
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound

from database.db_models import GameInfoDB, SceneDB
from services.command.scene_command_service import SceneCommandService
from services.command.talent_command_service import TalentCommandService
from services.command.tour_command_service import TourCommandService
from services.command.contract_command_service import ContractCommandService
from services.market_service import MarketService
from services.models.results import WeekAdvancementResult
from utils import time_utils

logger = logging.getLogger(__name__)

class TimeService:
    def __init__(self, session_factory, signals, scene_command_service: SceneCommandService,
                 talent_command_service: TalentCommandService, market_service: MarketService,
                 tour_command_service: TourCommandService, contract_service: ContractCommandService):
        self.session_factory = session_factory
        self.signals = signals
        self.scene_command_service = scene_command_service
        self.talent_command_service = talent_command_service
        self.market_service = market_service
        self.tour_command_service = tour_command_service
        self.contract_service = contract_service

    def _get_current_absolute_week(self, session: Session) -> int:
        """
        Reads the current time from the database, returning it as an absolute week.
        Handles one-time migration from old (week, year) format.
        """
        try:
            # Prefer the new 'absolute_week' key
            abs_week_info = session.query(GameInfoDB).filter_by(key='absolute_week').one()
            return int(abs_week_info.value)
        except NoResultFound:
            # Fallback/Migration from old (week, year) format
            logger.info("Migrating time from (week, year) to absolute_week format...")
            week_info = session.query(GameInfoDB).filter_by(key='week').one_or_none()
            year_info = session.query(GameInfoDB).filter_by(key='year').one_or_none()

            if not week_info or not year_info:
                # Handle case where db is fresh and has neither old nor new keys
                logger.warning("No time information found in DB. Initializing to week 1.")
                start_year = time_utils.STARTING_YEAR
                start_week = 1
                absolute_week = time_utils.to_absolute(start_year, start_week)
                session.add(GameInfoDB(key='absolute_week', value=str(absolute_week)))
                if week_info: session.delete(week_info)
                if year_info: session.delete(year_info)
                return absolute_week

            current_week = int(week_info.value)
            current_year = int(year_info.value)
            
            absolute_week = time_utils.to_absolute(current_year, current_week)
            
            session.add(GameInfoDB(key='absolute_week', value=str(absolute_week)))
            session.delete(week_info)
            session.delete(year_info)
            
            logger.info("Successfully migrated time to absolute_week.")
            return absolute_week

    def advance_week(self) -> WeekAdvancementResult:
        """Orchestrates all weekly game state changes within a single transaction."""
        session = self.session_factory()
        current_absolute_week_before_advance = -1
        try:
            current_absolute_week = self._get_current_absolute_week(session)
            current_absolute_week_before_advance = current_absolute_week

            money_info = session.query(GameInfoDB).filter_by(key='money').one()

            # --- 0. Process Contracts (Salaries & Compliance) ---
            self.contract_service.process_weekly_contracts(session, current_absolute_week)
            # Money is now handled inside contract service
            current_money = int(float(money_info.value))
        
            # --- 1. Perform all weekly updates ---
            self.tour_command_service.process_weekly_tour_updates(session, current_absolute_week)
            market_changed = self.market_service.recover_all_market_saturation(session)
            
            scenes_to_shoot = session.query(SceneDB).filter_by(
                status='scheduled',
                scheduled_absolute_week=current_absolute_week
            ).all()

            talents_who_worked_ids = set()
            scenes_shot_count = 0
            for scene_db in scenes_to_shoot:
                event_occurred = self.scene_command_service.shoot_scene(session, scene_db)
                scenes_shot_count += 1
                if event_occurred:
                    session.commit()
                    return WeekAdvancementResult(
                        new_absolute_week=current_absolute_week,
                        new_money=int(float(money_info.value)),
                        was_paused=True, scenes_shot=scenes_shot_count,
                        market_changed=market_changed
                    )
                for cast_member in scene_db.cast:
                    talents_who_worked_ids.add(cast_member.talent_id)

            edited_scenes = self.scene_command_service.process_weekly_post_production(session)

            next_absolute_week = current_absolute_week + 1
            is_new_year = time_utils.is_new_year_roll_over(next_absolute_week)

            talent_pool_changed = self.talent_command_service.process_weekly_updates(session, is_new_year, talents_who_worked_ids)
            
            self.tour_command_service.process_autonomous_tour_decisions(session, current_absolute_week)

            # --- 2. Persist the new time ---
            abs_week_info = session.query(GameInfoDB).filter_by(key='absolute_week').one()
            abs_week_info.value = str(next_absolute_week)
            
            # --- 3. Commit and return result ---
            session.commit()
            
            return WeekAdvancementResult(
                new_absolute_week=next_absolute_week,
                new_money=int(float(money_info.value)),
                scenes_shot=scenes_shot_count, scenes_edited=len(edited_scenes),
                market_changed=market_changed, talent_pool_changed=talent_pool_changed
            )
        except Exception as e:
            logger.error(f"Error during week advancement: {e}", exc_info=True)
            session.rollback()
            # Return current state on failure
            if current_absolute_week_before_advance != -1:
                money_val = session.query(GameInfoDB).filter_by(key='money').one_or_none()
                current_money = int(float(money_val.value)) if money_val else 0
                return WeekAdvancementResult(new_absolute_week=current_absolute_week_before_advance, new_money=current_money, was_paused=True)
            else:
                return WeekAdvancementResult(new_absolute_week=1, new_money=0, was_paused=True)
        finally:
            session.close()