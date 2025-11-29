import logging
from sqlalchemy.orm import Session, selectinload

from core.game_signals import GameSignals
from data.game_state import Talent
from database.db_models import TalentDB, TourDB, GameInfoDB, StudioStateDB
from services.models.configs import TourConfig
from services.command.casting_command_service import CastingCommandService
from services.query.game_query_service import GameQueryService
from services.query.talent_query_service import TalentQueryService
from services.query.talent_location_service import TalentLocationService
from services.calculation.talent_demand_calculator import TalentDemandCalculator
from services.calculation.trait_modifier_resolver import TraitModifierResolver
from services.calculation.tour_interest_calculator import TourInterestCalculator

logger = logging.getLogger(__name__)

class TourCommandService:
    """
    Command service for creating and managing talent tours.
    """
    def __init__(self, session_factory, signals: GameSignals,
                 casting_command_service: CastingCommandService, game_query_service: GameQueryService,
                 talent_query_service: TalentQueryService, talent_location_service: TalentLocationService,
                 demand_calculator: TalentDemandCalculator, trait_resolver: TraitModifierResolver,
                 interest_calculator: TourInterestCalculator, config: TourConfig):
        self.session_factory = session_factory
        self.signals = signals
        self.casting_command_service = casting_command_service
        self.game_query_service = game_query_service
        self.talent_query_service = talent_query_service
        self.talent_location_service = talent_location_service
        self.demand_calculator = demand_calculator
        self.trait_resolver = trait_resolver
        self.interest_calculator = interest_calculator
        self.config = config

    def sponsor_tour(self, talent_id: int, roles_to_cast: list, tour_details: dict, total_upfront_cost: int) -> bool:
        """
        Player-initiated action that sponsors a tour AND casts the talent in a set of
        roles, all within a single, atomic transaction. This method trusts the
        pre-calculated cost from the UI/orchestrator.
        """
        session = self.session_factory()
        try:
            talent_db = session.query(TalentDB).get(talent_id)
            if not talent_db: return False

            # --- 1. Financials (Trust, Don't Verify) ---
            studio_state = session.query(StudioStateDB).get(1)
            current_money = studio_state.money
            new_money = current_money - total_upfront_cost
            studio_state.money = new_money

            # --- 2. Create Tour Record ---
            new_tour = TourDB(
                talent_id=talent_id, status='planned', sponsor_type='player',
                upfront_fee_paid=total_upfront_cost, **tour_details
            )
            session.add(new_tour)

            end_absolute_week = new_tour.start_absolute_week + new_tour.duration_weeks
            talent_db.tour_end_absolute_week = end_absolute_week
            
            # --- 3. Orchestration: Calculate authoritative final salaries for the roles ---
            abs_week_info = session.query(GameInfoDB).filter_by(key='absolute_week').one()
            current_absolute_week = int(abs_week_info.value)
            talent_dc = self.game_query_service.get_talent_by_id(talent_id)

            roles_with_context = []
            for role in roles_to_cast:
                scene_dc = self.game_query_service.get_scene_by_id(role['scene_id'])
                roles_with_context.append({
                    'scene': scene_dc,
                    'virtual_performer_id': role['virtual_performer_id'],
                    'bloc_id': scene_dc.bloc_id,
                    'talent_effective_location': tour_details['destination_location']
                })
            
            cost_results = self.demand_calculator.calculate_bulk_hiring_costs(
                talent_dc, roles_with_context, current_absolute_week
            )
            roles_with_final_salaries = cost_results['roles_with_final_salaries']

            hiring_data = {
                'roles': roles_with_final_salaries,
                'upfront_cost': 0
            }

            # --- 4. Delegate Casting to CastingCommandService ---
            self.casting_command_service.cast_roles_with_precalculated_salaries(session, talent_id, hiring_data)
 
            # --- 5. Commit & Signal ---
            session.commit()
            self.signals.money_changed.emit(new_money)
            self.signals.notification_posted.emit(f"Sponsored tour and hired {talent_db.alias} for {len(roles_to_cast)} roles. Upfront cost: ${total_upfront_cost:,}")
            self.signals.scenes_changed.emit()
            self.signals.roster_changed.emit()
            return True
        except Exception as e:
            logger.error(f"Error in sponsoring tour for talent {talent_id}: {e}", exc_info=True)
            session.rollback()
            return False
        finally:
            session.close()

    def process_autonomous_tour_decisions(self, session: Session, current_absolute_week: int):
        """
        Evaluates a batch of talents to see if they want to book their own tours.
        """
        batch_size = self.config.batch_size
        if batch_size <= 0: batch_size = 1

        target_remainder = current_absolute_week % batch_size
        
        candidates_db = (
            session.query(TalentDB)
            .filter(
                TalentDB.id % batch_size == target_remainder,
                TalentDB.is_on_tour == False
            )
            .all()
        )

        if not candidates_db:
            return

        candidate_ids = [t.id for t in candidates_db]
        
        workloads = self.talent_query_service.get_recent_workload_counts(
            candidate_ids, current_absolute_week
        )

        tours_created = 0
        for talent_db in candidates_db:
            talent_dc = talent_db.to_dataclass(Talent)
            workload = workloads.get(talent_db.id, 0)

            dest, duration = self.interest_calculator.calculate_tour_decision(
                talent_dc, workload, current_absolute_week
            )

            if dest:
                start_absolute_week = current_absolute_week + 2

                new_tour = TourDB(
                    talent_id=talent_db.id,
                    status='planned',
                    sponsor_type='self',
                    destination_location=dest,
                    start_absolute_week=start_absolute_week,
                    duration_weeks=duration,
                    accommodation_tier_id='basic',
                    upfront_fee_paid=0
                )
                session.add(new_tour)
                
                end_absolute_week = start_absolute_week + duration
                talent_db.tour_end_absolute_week = end_absolute_week

                tours_created += 1
                self.signals.notification_posted.emit(f"Autonomous Tour: {talent_db.alias} decided to go to {dest} for {duration} weeks.")

        if tours_created > 0:
            self.signals.notification_posted.emit(f"{tours_created} talents have booked their own tours.")

    def process_weekly_tour_updates(self, session: Session, current_absolute_week: int):
        """
        Updates tour statuses from 'planned' to 'active' or 'active' to 'completed'.
        """
        # --- Start planned tours ---
        tours_to_start = session.query(TourDB).filter_by(
            status='planned', start_absolute_week=current_absolute_week
        ).options(selectinload(TourDB.talent)).all()

        for tour in tours_to_start:
            tour.status = 'active'
            tour.talent.is_on_tour = True
            tour.talent.current_location = tour.destination_location
            self.signals.notification_posted.emit(f"Tour for {tour.talent.alias} to {tour.destination_location} is now active.")

        # --- End active tours ---
        active_tours = session.query(TourDB).filter_by(status='active').options(selectinload(TourDB.talent)).all()
        for tour in active_tours:
            end_absolute_week = tour.start_absolute_week + tour.duration_weeks
            
            if current_absolute_week >= end_absolute_week:
                tour.status = 'completed'
                tour.talent.is_on_tour = False
                tour.talent.current_location = tour.talent.base_location
                
                # The tour_end_absolute_week was set when the tour was created/sponsored.
                # This ensures the cooldown period is calculated correctly from this date.
                self.signals.notification_posted.emit(f"Tour for {tour.talent.alias} has ended.")

