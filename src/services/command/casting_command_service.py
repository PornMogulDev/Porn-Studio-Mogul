import logging
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from core.game_signals import GameSignals
from database.db_models import SceneDB, SceneCastDB, GameInfoDB
from services.query.game_query_service import GameQueryService
from services.calculation.talent_demand_calculator import TalentDemandCalculator
from services.query.talent_location_service import TalentLocationService

logger = logging.getLogger(__name__)

class CastingCommandService:
    """
    Command service for casting-related database operations.
    """
    def __init__(self, session_factory, signals: GameSignals, query_service: GameQueryService,
                 location_service: TalentLocationService, demand_calculator: TalentDemandCalculator):
        self.session_factory = session_factory
        self.signals = signals
        self.query_service = query_service
        self.demand_calculator = demand_calculator
        self.location_service = location_service

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
    
    def _cast_talent_for_multiple_roles_internal(self, session: Session, talent_id: int, roles: List[Dict], is_tour_casting: bool = False):
        """
        Internal helper for multi-casting logic. Operates on the provided session.
        If is_tour_casting is True, it assumes upfront costs have already been paid.
        """
        if not is_tour_casting:
             # --- 1. Orchestration: Prepare data for the pure calculator ---
            game_info = {row.key: row.value for row in session.query(GameInfoDB).filter(GameInfoDB.key.in_(['week', 'year'])).all()}
            current_week = int(game_info.get('week', 1))
            current_year = int(game_info.get('year', 0))
            talent_dc = self.query_service.get_talent_by_id(talent_id)
            if not talent_dc: raise ValueError(f"Talent with ID {talent_id} not found.")

            roles_with_context = []
            for role in roles:
                scene_id = role['scene_id']
                scene_dc = self.query_service.get_scene_by_id(scene_id)
                if not scene_dc: raise ValueError(f"Scene with ID {scene_id} not found.")
                
                talent_loc = self.location_service.get_effective_location_at_date(
                    talent_id, scene_dc.scheduled_week, scene_dc.scheduled_year
                )
                roles_with_context.append({
                    'scene': scene_dc,
                    'virtual_performer_id': role['virtual_performer_id'],
                    'bloc_id': scene_dc.bloc_id,
                    'talent_effective_location': talent_loc
                })

            # --- 2. Get authoritative costs from the pure calculator service ---
            cost_results = self.demand_calculator.calculate_bulk_hiring_costs(
                talent_dc, roles_with_context, current_week, current_year
            )
            if not cost_results: raise ValueError("Could not calculate hiring costs.")

            # --- 3. Apply changes to the database ---
            # Deduct upfront costs (travel fees)
            money_info = session.query(GameInfoDB).filter_by(key='money').one()
            current_money = int(float(money_info.value))
            new_money = current_money - cost_results['total_upfront_cost']
            money_info.value = str(new_money)

            # Cast each role with its final, discounted salary
            for role_data in cost_results['roles_with_final_salaries']:
                self._cast_talent_for_role_internal(
                    session, talent_id, role_data['scene_id'], 
                    role_data['virtual_performer_id'], role_data['final_salary']
                )
            return new_money, cost_results['total_upfront_cost']
        else:
            # For tour casting, upfront costs are handled by TourCommandService.
            # We just need to cast with the salaries passed in.
            for role_data in roles:
                self._cast_talent_for_role_internal(
                    session, talent_id, role_data['scene_id'], 
                    role_data['virtual_performer_id'], role_data['final_salary']
                )
            return None, None # No money change to report from here

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
            new_money, upfront_cost = self._cast_talent_for_multiple_roles_internal(session, talent_id, roles)

            session.commit()
            self.signals.notification_posted.emit(f"Successfully hired talent in {len(roles)} role(s). Upfront cost: ${upfront_cost:,}")
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