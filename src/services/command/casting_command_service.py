import logging
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from core.game_signals import GameSignals
from database.db_models import SceneDB, SceneCastDB, GameInfoDB
from services.query.game_query_service import GameQueryService
from services.calculation.talent_demand_calculator import TalentDemandCalculator

logger = logging.getLogger(__name__)

class CastingCommandService:
    """
    Command service for casting-related database operations.
    """
    def __init__(self, session_factory, signals: GameSignals, query_service: GameQueryService, demand_calculator: TalentDemandCalculator):
        self.session_factory = session_factory
        self.signals = signals
        self.query_service = query_service
        self.demand_calculator = demand_calculator

    def _cast_talent_for_role_internal(self, session: Session, talent_id: int, scene_id: int, virtual_performer_id: int, cost: int) -> Optional[Dict]:
        """
        Internal helper for casting logic. Does NOT commit.
        Receives session as parameter to work within caller's transaction.
        """
        scene_db = session.query(SceneDB).get(scene_id)
        talent = self.query_service.get_talent_by_id(talent_id)
        if not scene_db or not talent: return None

        new_cast_entry = SceneCastDB(
            scene_id=scene_id, talent_id=talent_id,
            virtual_performer_id=virtual_performer_id, salary=cost
        )
        scene_db.cast.append(new_cast_entry)

        messages = {
            "main_message": f"Cast {talent.alias} in '{scene_db.title}' for ${cost:,}.",
            "locked_message": None, "complete_message": None
        }

        if not scene_db.is_locked:
            scene_db.is_locked = True
            messages["locked_message"] = f"Scene '{scene_db.title}' is now locked for design changes."

        if len(scene_db.cast) == len(scene_db.virtual_performers):
            scene_db.status = 'scheduled'
            messages["complete_message"] = f"Casting complete! '{scene_db.title}' is now scheduled."
        
        return messages
    
    def cast_talent_for_role(self, talent_id: int, scene_id: int, virtual_performer_id: int, cost: int) -> bool:
        """Public method for casting a single talent. Creates and manages its own session."""
        session = self.session_factory()
        try:
            result = self._cast_talent_for_role_internal(session, talent_id, scene_id, virtual_performer_id, cost)
            if result:
                session.commit()
                self.signals.notification_posted.emit(result['main_message'])
                if result['locked_message']: self.signals.notification_posted.emit(result['locked_message'])
                if result['complete_message']: self.signals.notification_posted.emit(result['complete_message'])
                self.signals.scenes_changed.emit()
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error casting talent {talent_id} for role {virtual_performer_id} in scene {scene_id}: {e}", exc_info=True)
            return False
        finally:
            session.close()

    def cast_talent_for_multiple_roles(self, talent_id: int, roles: List[Dict]) -> bool:
        """Casts a single talent for multiple roles within a single transaction."""
        session = self.session_factory()
        try:           
            # 1. Get authoritative costs from the calculator service
            game_info = {row.key: row.value for row in session.query(GameInfoDB).filter(GameInfoDB.key.in_(['week', 'year', 'studio_location'])).all()}
            current_week = int(game_info.get('week', 1))
            current_year = int(game_info.get('year', 0))
            studio_location = game_info.get('studio_location', '')

            cost_results = self.demand_calculator.calculate_bulk_hiring_costs(
                talent_id, roles, studio_location, current_week, current_year
            )

            if not cost_results:
                raise ValueError("Could not calculate hiring costs.")

            # 2. Deduct upfront costs (travel fees)
            money_info = session.query(GameInfoDB).filter_by(key='money').one()
            current_money = int(float(money_info.value))
            new_money = current_money - cost_results['total_upfront_cost']
            money_info.value = str(new_money)

            # 3. Cast each role with its final, discounted salary
            for role_data in cost_results['roles_with_final_salaries']:
                self._cast_talent_for_role_internal(
                    session, talent_id, role_data['scene_id'], 
                    role_data['virtual_performer_id'], role_data['final_salary']
                )

            session.commit()
            self.signals.notification_posted.emit(f"Successfully hired talent in {len(roles)} role(s). Upfront cost: ${cost_results['total_upfront_cost']:,}")
            self.signals.money_changed.emit(new_money)
            self.signals.scenes_changed.emit()
            return True
        except Exception as e:
            logger.error(f"Error in multi-cast for talent {talent_id}: {e}", exc_info=True)
            session.rollback()
            self.signals.notification_posted.emit(f"An error occurred during multi-casting. Operation cancelled.")
            return False
        finally:
            session.close()