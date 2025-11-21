import logging
from sqlalchemy.orm import Session, selectinload

from core.game_signals import GameSignals
from data.game_state import Talent
from database.db_models import TalentDB, TourDB, GameInfoDB
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
            money_info = session.query(GameInfoDB).filter_by(key='money').one()
            current_money = int(float(money_info.value))
            new_money = current_money - total_upfront_cost
            money_info.value = str(new_money)

            # --- 2. Create Tour Record ---
            new_tour = TourDB(
                talent_id=talent_id, status='planned', sponsor_type='player',
                upfront_fee_paid=total_upfront_cost, **tour_details
            )
            session.add(new_tour)
            
            # --- 3. Orchestration: Calculate authoritative final salaries for the roles ---
            game_info = {row.key: row.value for row in session.query(GameInfoDB).filter(GameInfoDB.key.in_(['week', 'year'])).all()}
            current_week = int(game_info.get('week', 1))
            current_year = int(game_info.get('year', 0))
            talent_dc = self.game_query_service.get_talent_by_id(talent_id)

            roles_with_context = []
            for role in roles_to_cast:
                scene_dc = self.game_query_service.get_scene_by_id(role['scene_id'])
                # For tour casting, the talent's effective location *is* the tour destination
                # for all scenes within the tour period.
                roles_with_context.append({
                    'scene': scene_dc,
                    'virtual_performer_id': role['virtual_performer_id'],
                    'bloc_id': scene_dc.bloc_id,
                    'talent_effective_location': tour_details['destination_location']
                })
            
            # Note: The 'total_upfront_cost' from the calculator here is for travel *between scenes* on the tour,
            # which is assumed to be 0 since they are all in the same location. The main upfront cost (travel
            # to destination + accommodation) has already been handled. We only need the final salaries.
            cost_results = self.demand_calculator.calculate_bulk_hiring_costs(
                talent_dc, roles_with_context, current_week, current_year
            )
            roles_with_final_salaries = cost_results['roles_with_final_salaries']

            # Prepare the authoritative payload for the casting service.
            # The upfront_cost here is 0 because inter-role travel on a tour is nil.
            hiring_data = {
                'roles': roles_with_final_salaries,
                'upfront_cost': 0
            }

            # --- 4. Delegate Casting to CastingCommandService ---
            # Call the new public method, passing the active session to ensure atomicity.
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

    def process_autonomous_tour_decisions(self, session: Session):
        """
        Evaluates a batch of talents to see if they want to book their own tours.
        """
        game_info = session.query(GameInfoDB).all()
        info_dict = {g.key: int(g.value) for g in game_info if g.key in ['week', 'year']}
        current_week = info_dict.get('week', 1)
        current_year = info_dict.get('year', 1)

        batch_size = self.config.batch_size
        if batch_size <= 0: batch_size = 1

        # 1. Query Batch
        # Formula: id % batch_size == current_week % batch_size
        # Filter: Not on tour
        target_remainder = current_week % batch_size
        
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
        
        # 2. Bulk Fetch Workload Data
        workloads = self.talent_query_service.get_recent_workload_counts(
            candidate_ids, current_week, current_year
        )

        # 3. Process Decisions
        tours_created = 0
        for talent_db in candidates_db:
            talent_dc = talent_db.to_dataclass(Talent) # Needed for trait logic
            workload = workloads.get(talent_db.id, 0)

            dest, duration = self.interest_calculator.calculate_tour_decision(
                talent_dc, workload, current_week, current_year
            )

            if dest:
                # Create the tour!
                # Start week is usually "next week" or 2 weeks out. Let's say 2 weeks out.
                start_week = current_week + 2
                start_year = current_year
                if start_week > 52:
                    start_week -= 52
                    start_year += 1

                new_tour = TourDB(
                    talent_id=talent_db.id,
                    status='planned',
                    sponsor_type='self', # Important
                    destination_location=dest,
                    start_week=start_week,
                    start_year=start_year,
                    duration_weeks=duration,
                    accommodation_tier_id='basic', # Self-funded defaults
                    upfront_fee_paid=0
                )
                session.add(new_tour)
                
                # Update Talent State to prevent double booking
                talent_db.is_on_tour = True # Mark as booked immediately or wait? 
                # Usually we mark is_on_tour only when it becomes 'active'.
                # But we should set the tour_end_week to reserve the time.
                end_abs = (start_year * 52 + start_week) + duration
                e_year, e_week_rem = divmod(end_abs - 1, 52)
                talent_db.tour_end_year = e_year
                talent_db.tour_end_week = e_week_rem + 1

                tours_created += 1
                self.signals.notification_posted.emit(f"Autonomous Tour: {talent_db.alias} decided to go to {dest} for {duration} weeks.")

        if tours_created > 0:
            self.signals.notification_posted.emit(f"{tours_created} talents have booked their own tours.")

    def process_weekly_tour_updates(self, session: Session, current_week: int, current_year: int):
        """
        Updates tour statuses.
        """
        # --- Start planned tours ---
        tours_to_start = session.query(TourDB).filter_by(
            status='planned', start_week=current_week, start_year=current_year
        ).options(selectinload(TourDB.talent)).all()

        for tour in tours_to_start:
            tour.status = 'active'
            tour.talent.is_on_tour = True
            tour.talent.current_location = tour.destination_location
            self.signals.notification_posted.emit(f"Tour for {tour.talent.alias} to {tour.destination_location} is now active.")

        # --- End active tours ---
        active_tours = session.query(TourDB).filter_by(status='active').options(selectinload(TourDB.talent)).all()
        for tour in active_tours:
            end_week = tour.start_week + tour.duration_weeks
            end_year = tour.start_year
            if end_week > 52:
                end_year += (end_week - 1) // 52
                end_week = (end_week - 1) % 52 + 1
            
            if current_year > end_year or (current_year == end_year and current_week >= end_week):
                tour.status = 'completed'
                tour.talent.is_on_tour = False
                tour.talent.current_location = tour.talent.base_location
                
                # KEY CHANGE: We do NOT reset tour_end_week/year to 0.
                # We leave them as the date the tour ended.
                # This allows the history check in the calculator to work.
                
                self.signals.notification_posted.emit(f"Tour for {tour.talent.alias} has ended.")
