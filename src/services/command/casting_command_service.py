import logging
from typing import Dict, List, Optional
from sqlalchemy.orm import Session, selectinload

from core.game_signals import GameSignals
from database.db_models import SceneDB, SceneCastDB, GameInfoDB, ActionSegmentDB, TalentDB
from data.game_state import Scene, Talent
from services.command.contract_command_service import ContractCommandService
from services.query.game_query_service import GameQueryService
from services.calculation.talent_demand_calculator import TalentDemandCalculator
from services.calculation.shoot_results_calculator import ShootResultsCalculator
from services.calculation.bulk_booking_validator import BulkBookingValidator
from services.query.talent_location_service import TalentLocationService

logger = logging.getLogger(__name__)

class CastingCommandService:
    """
    Command service for casting-related database operations.
    """
    def __init__(self, session_factory, signals: GameSignals, query_service: GameQueryService,
                 location_service: TalentLocationService, demand_calculator: TalentDemandCalculator,
                 shoot_results_calculator: ShootResultsCalculator, contract_service: ContractCommandService):
        self.session_factory = session_factory
        self.signals = signals
        self.query_service = query_service
        self.demand_calculator = demand_calculator
        self.location_service = location_service
        self.shoot_results_calculator = shoot_results_calculator
        self.contract_command_service = contract_service

    def _cast_talent_for_role_internal(self, session: Session, talent_db: TalentDB, scene_db: SceneDB, virtual_performer_id: int, cost: int) -> Optional[Dict]:
        """
        Internal helper for casting logic. Does NOT commit.
        Refactored to accept scene_db object to prevent N+1 queries in loops.
        """
        # Contract Override Logic
        if talent_db.contract:
            cost = 0
            # Calculate compliance impact
            talent_dc = talent_db.to_dataclass(Talent)
            pref_score = self.demand_calculator.get_role_preference_score(talent_dc, scene_db.to_dataclass(Scene), virtual_performer_id)
            self.contract_command_service.update_compliance(session, talent_db.id, pref_score)

        new_cast_entry = SceneCastDB(
            scene_id=scene_db.id, talent_id=talent_db.id,
            virtual_performer_id=virtual_performer_id, salary=cost
        )
        scene_db.cast.append(new_cast_entry)

        messages = {
            "main_message": f"Cast {talent_db.alias} in '{scene_db.title}' for ${cost:,}.",
            "locked_message": None, "complete_message": None
        }

        if not scene_db.is_locked:
            scene_db.is_locked = True
            messages["locked_message"] = f"Scene '{scene_db.title}' is now locked for design changes."

        if len(scene_db.cast) == len(scene_db.virtual_performers):
            scene_db.status = 'scheduled'
            messages["complete_message"] = f"Casting complete! '{scene_db.title}' is now scheduled."
        
        return messages
    
    def cast_roles_with_precalculated_salaries(self, session: Session, talent_id: int, hiring_data: Dict) -> tuple[int, int]:
        """
        Casts a talent for multiple roles using authoritative costs (salaries and
        upfront fees) calculated by an orchestrator. This is the sole entry
        point for complex, multi-role casting actions.
        Now includes a strict guardrail validation to prevent abuse.
        """
        upfront_cost = hiring_data.get('upfront_cost', 0)
        roles_with_salaries = hiring_data.get('roles', [])

        # --- 1. Apply changes to the database ---
        # Deduct upfront costs (e.g., travel fees). For tours, this will be 0
        # as the main tour cost is handled by TourCommandService.
        money_info = session.query(GameInfoDB).filter_by(key='money').one()
        current_money = int(float(money_info.value))
        new_money = current_money - upfront_cost
        money_info.value = str(new_money)

        # --- 2. Guardrail: Validate Bulk Booking Constraints ---
        # We must ensure the client/UI didn't bypass fatigue or weekly limits.
        talent_db = session.query(TalentDB).options(selectinload(TalentDB.contract)).get(talent_id)
        if not talent_db: raise ValueError("Talent not found")
        talent_dc = talent_db.to_dataclass(Talent)

        game_week = int(session.query(GameInfoDB).filter_by(key='week').one().value)
        game_year = int(session.query(GameInfoDB).filter_by(key='year').one().value)
        
        # Fetch existing bookings for validation context
        # Since we are in a session, we do a direct query to avoid detachment issues
        # We convert to Dataclass to satisfy Validator requirements
        existing_bookings_db = session.query(SceneDB).join(SceneCastDB).filter(SceneCastDB.talent_id == talent_id).all()
        existing_bookings = [s.to_dataclass(Scene) for s in existing_bookings_db]
        
        validator = BulkBookingValidator(
            current_week=game_week,
            current_year=game_year,
            talent=talent_dc,  
            existing_bookings=existing_bookings,
           hiring_config=self.demand_calculator.hiring_config,
            shoot_calculator=self.shoot_results_calculator
        )

        # Pre-fetch scenes to avoid repeated queries inside the loop
        scene_ids = [r['scene_id'] for r in roles_with_salaries]
        # We must eager load segments to convert to dataclass correctly for calculation
        scenes_db = session.query(SceneDB).options(
            selectinload(SceneDB.action_segments).selectinload(ActionSegmentDB.slot_assignments)
        ).filter(SceneDB.id.in_(scene_ids)).all()
        
        scenes_map = {s.id: s for s in scenes_db}

        # Cast each role with its final, authoritative salary
        for role_data in roles_with_salaries:
            scene_db = scenes_map.get(role_data['scene_id'])
            if not scene_db: continue

            # Validate using dataclass (required for logic methods like get_expanded_action_segments)
            result = validator.try_book_role(scene_db.to_dataclass(Scene), role_data['virtual_performer_id'])
            if not result.success:
                raise ValueError(f"Booking rejected by guardrail: {result.reason}")

            self._cast_talent_for_role_internal(
                session, talent_db, scene_db, 
                role_data['virtual_performer_id'], role_data['final_salary']
            )
        return new_money, upfront_cost

    def cast_talent_for_role(self, talent_id: int, scene_id: int, virtual_performer_id: int, cost: int) -> bool:
        """Public method for casting a single talent. Creates and manages its own session."""
        session = self.session_factory()
        try:
            scene_db = session.query(SceneDB).get(scene_id)
            talent_db = session.query(TalentDB).options(selectinload(TalentDB.contract)).get(talent_id)
            
            if not scene_db or not talent_db: return False

            result = self._cast_talent_for_role_internal(session, talent_db, scene_db, virtual_performer_id, cost)
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

    def cast_talent_for_multiple_roles(self, talent_id: int, hiring_data: Dict) -> bool:
        """Casts a single talent for multiple roles within a single transaction."""
        session = self.session_factory()
        try:
            new_money, upfront_cost = self.cast_roles_with_precalculated_salaries(session, talent_id, hiring_data)

            session.commit()
            num_roles = len(hiring_data.get('roles', []))
            self.signals.notification_posted.emit(f"Successfully hired talent in {num_roles} role(s). Upfront cost: ${upfront_cost:,}")
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