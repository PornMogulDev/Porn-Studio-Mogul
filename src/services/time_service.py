import logging

from database.db_models import GameInfoDB, SceneDB, StudioStateDB
from services.command.scene_command_service import SceneCommandService
from services.command.talent_command_service import TalentCommandService
from services.command.tour_command_service import TourCommandService
from services.command.contract_command_service import ContractCommandService
from services.ai.ai_studio_director import AIStudioDirector
from services.market_service import MarketService
from services.models.results import WeekAdvancementResult
from utils import time_utils

logger = logging.getLogger(__name__)

class TimeService:
    def __init__(self, session_factory, signals, scene_command_service: SceneCommandService,
                 talent_command_service: TalentCommandService, market_service: MarketService,
                 tour_command_service: TourCommandService, contract_service: ContractCommandService,
                 ai_studio_director: AIStudioDirector):
        self.session_factory = session_factory
        self.signals = signals
        self.scene_command_service = scene_command_service
        self.talent_command_service = talent_command_service
        self.market_service = market_service
        self.tour_command_service = tour_command_service
        self.contract_service = contract_service
        self.ai_studio_director = ai_studio_director

    def advance_week(self) -> WeekAdvancementResult:
        """Orchestrates all weekly game state changes within a single transaction."""
        session = self.session_factory()
        current_absolute_week = 0
        try:
            # Fetch current time directly (Database is assumed to be initialized correctly by GameSessionService)
            abs_week_info = session.query(GameInfoDB).filter_by(key='absolute_week').one()
            current_absolute_week = int(abs_week_info.value)

            studio_state = session.query(StudioStateDB).get(1)
            
            # --- 0. Process Contracts (Salaries & Compliance) ---
            self.contract_service.process_weekly_contracts(session, current_absolute_week)
            
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
                        new_money=studio_state.money,
                        was_paused=True, scenes_shot=scenes_shot_count,
                        market_changed=market_changed
                    )
                for cast_member in scene_db.cast:
                    talents_who_worked_ids.add(cast_member.talent_id)

            edited_scenes = self.scene_command_service.process_weekly_post_production(session)

            next_absolute_week = current_absolute_week + 1
            is_new_year = time_utils.is_new_year_roll_over(next_absolute_week)

            talent_pool_changed = self.talent_command_service.process_weekly_updates(session, is_new_year, talents_who_worked_ids)

            # Capture if emails were changed
            emails_changed = self.tour_command_service.process_autonomous_tour_decisions(session, current_absolute_week)
            
            # --- Process AI Studio Actions ---
            if self.ai_studio_director:
                self.ai_studio_director.process_weekly_ai_decisions(session, current_absolute_week)
                # NOTE: If AI Director starts generating emails (e.g. sponsorship offers), 
                # we should capture a return value here too. For now assuming False.

            # --- 2. Persist the new time ---
            abs_week_info.value = str(next_absolute_week)
            
            # --- 3. Commit and return result ---
            session.commit()
            
            return WeekAdvancementResult(
                new_absolute_week=next_absolute_week, new_money=studio_state.money,
                scenes_shot=scenes_shot_count, scenes_edited=len(edited_scenes),
                market_changed=market_changed, talent_pool_changed=talent_pool_changed,
                emails_changed=emails_changed
            )
        except Exception as e:
            logger.error(f"Error during week advancement: {e}", exc_info=True)
            session.rollback()
            # Return current state on failure
            studio_state = session.query(StudioStateDB).get(1)
            current_money = studio_state.money if studio_state else 0
            # If current_absolute_week was never set (exception during fetch), fallback to 1
            safe_week = current_absolute_week if current_absolute_week > 0 else 1
            
            return WeekAdvancementResult(new_absolute_week=safe_week, new_money=current_money, was_paused=True)
        finally:
            session.close()