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
    """
    Orchestrates weekly game state progression.
    
    SESSION MANAGEMENT PATTERN: Multi-Step Transaction with Session Passing
    =======================================================================
    
    Architecture:
    -------------
    This service orchestrates complex multi-step operations that must be atomic.
    It creates one session for the entire transaction and passes it to helper
    methods/services that perform individual steps.
    
    Key Principles:
    ---------------
    1. Orchestrator creates ONE session for the entire transaction
    2. Session is passed to helper methods/services
    3. Helpers DO NOT commit (orchestrator commits once at the end)
    4. Single commit point ensures atomicity
    5. Early return with commit if operation is paused (e.g., events)
    6. Use try/except/finally for proper error handling
    
    Pattern Template:
    -----------------
    def orchestrate_operation(self) -> Result:
        '''Main orchestrator for multi-step operation.'''
        session = self.session_factory()
        try:
            # Step 1: Call helper that receives session
            helper1_changed = self.helper_service.do_step1(session)
            
            # Step 2: Query and process
            items = session.query(Model).filter(...).all()
            for item in items:
                # Pass session to helper that shouldn't commit
                paused = self.other_service.process_item(session, item)
                if paused:
                    # Early commit and return
                    session.commit()
                    return Result(..., was_paused=True)
            
            # Step 3: More operations
            step3_result = self.another_helper(session)
            
            # All steps succeeded - single commit point
            session.commit()
            return Result(..., was_paused=False)
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error: {e}", exc_info=True)
            return Result(..., error=True)
        finally:
            session.close()
    
    Helper Method Signature:
    ------------------------
    Helpers receive session as parameter and do NOT commit:
    
    def helper_method(self, session: Session, ...) -> bool:
        '''Helper called by orchestrator. Does NOT commit.'''
        # Perform database operations using the passed session
        obj = session.query(Model).get(id)
        obj.field = new_value
        # NO session.commit() here!
        return success
    
    Benefits:
    ---------
    - Atomicity: All steps commit together or rollback together
    - Consistency: Intermediate state never visible to other transactions
    - Early exit: Can commit partial work and pause if needed
    - Clear ownership: Orchestrator owns the transaction lifecycle
    
    Example in This Service:
    ------------------------
    advance_week() orchestrates:
    1. Market recovery (helper receives session)
    2. Scene shooting (helper receives session, may pause for events)
    3. Post-production processing (helper receives session)
    4. Talent updates (helper receives session)
    5. Time advancement (direct modification)
    6. Single commit at end (or early commit if paused)
    """
    
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

            # Update post-production and advance time
            edited_scenes = self.scene_command_service.process_weekly_post_production(session)

            next_week, next_year = (current_week + 1, current_year)
            is_new_year = False
            if next_week > 52:
                    next_week = 1
                    next_year += 1
                    is_new_year = True

            talent_pool_changed = self.talent_command_service.process_weekly_updates(session, current_date_val, is_new_year)

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