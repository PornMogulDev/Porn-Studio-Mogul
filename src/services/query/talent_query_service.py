import logging
from typing import Dict, List, Set
from collections import defaultdict
from sqlalchemy.orm import selectinload, Session
from sqlalchemy import func

from data.game_state import Scene, Tour
from data.data_manager import DataManager
from database.db_models import (
    TalentDB, SceneDB, ActionSegmentDB, StudioStateDB,
    ShootingBlocDB, SceneCastDB, TourDB
)
from services.query.game_query_service import GameQueryService
from services.query.talent_location_service import TalentLocationService
from services.calculation.talent_demand_calculator import TalentDemandCalculator
from services.calculation.talent_status_calculator import TalentStatusCalculator
from services.models.results import WeeklyStatusResult
from services.models.configs import HiringConfig
from services.calculation.talent_availability_checker import TalentAvailabilityChecker
from services.calculation.shoot_results_calculator import ShootResultsCalculator
from utils import time_utils

logger = logging.getLogger(__name__)

class TalentQueryService:
    def __init__(self, session_factory, data_manager: DataManager, query_service: GameQueryService, location_service: TalentLocationService,
                 demand_calculator: TalentDemandCalculator, config: HiringConfig, availability_checker: TalentAvailabilityChecker, 
                 shoot_results_calculator: ShootResultsCalculator, status_calculator: TalentStatusCalculator):
        self.session_factory = session_factory
        self.data_manager = data_manager
        self.query_service = query_service
        self.location_service = location_service
        self.demand_calculator = demand_calculator
        self.config = config
        self.availability_checker = availability_checker
        self.shoot_results_calculator = shoot_results_calculator
        self.status_calculator = status_calculator

    def _get_role_tags_for_display(self, scene: Scene, vp_id: int) -> List[str]:
        """Helper to get a formatted list of tags and roles for UI display."""
        _, roles_by_tag = self.availability_checker.get_vp_role_context(scene, vp_id)
        tags_with_roles = [
            f"{tag_name} ({', '.join(sorted(list(roles)))})" 
            for tag_name, roles in sorted(roles_by_tag.items())
        ]
        return tags_with_roles
    
    def get_booked_bloc_ids(self, talent_id: int) -> Set[int]:
        """Fetches the set of bloc IDs the talent is currently booked for."""
        with self.session_factory() as session:
            bloc_ids = session.query(SceneDB.bloc_id)\
                .join(SceneCastDB, SceneCastDB.scene_id == SceneDB.id)\
                .filter(SceneCastDB.talent_id == talent_id)\
                .filter(SceneDB.bloc_id.isnot(None))\
                .distinct()\
                .all()
            
            return {row[0] for row in bloc_ids}

    def get_booked_bloc_ids_for_multiple_talents(self, talent_ids: List[int]) -> Dict[int, Set[int]]:
        """
        Efficiently fetches booked bloc IDs for a list of talents in a single query.
        Returns: {talent_id: {bloc_id, bloc_id, ...}}
        """
        if not talent_ids:
            return {}
            
        with self.session_factory() as session:
            rows = session.query(SceneCastDB.talent_id, SceneDB.bloc_id)\
                .join(SceneDB, SceneCastDB.scene_id == SceneDB.id)\
                .filter(SceneCastDB.talent_id.in_(talent_ids))\
                .filter(SceneDB.bloc_id.isnot(None))\
                .distinct()\
                .all()
            
            result = defaultdict(set)
            for t_id, b_id in rows:
                result[t_id].add(b_id)
            
            return result

    def _get_bookings_by_absolute_week(self, session: Session, talent_ids: List[int]) -> Dict[int, Dict[int, List[Scene]]]:
        """Efficiently fetches all scene bookings for a list of talents, grouped by absolute_week and then by talent."""
        weekly_bookings = defaultdict(lambda: defaultdict(list))
        if not talent_ids:
            return weekly_bookings
            
        cast_entries = session.query(SceneCastDB).options(selectinload(SceneCastDB.scene)).filter(SceneCastDB.talent_id.in_(talent_ids)).all()

        for entry in cast_entries:
            if entry.scene.status == 'scheduled':
                weekly_bookings[entry.scene.scheduled_absolute_week][entry.talent_id].append(entry.scene)
        return weekly_bookings

    def get_talent_bookings_by_absolute_week(self, talent_id: int, start_absolute_week: int, end_absolute_week: int) -> Dict[int, List[Scene]]:
        """Efficiently fetches all scene bookings for a single talent for a given absolute week range, grouped by absolute week."""
        bookings_by_absolute_week = defaultdict(list)
        
        with self.session_factory() as session:
            cast_entries = session.query(SceneCastDB)\
                .join(SceneDB)\
                .filter(
                    SceneCastDB.talent_id == talent_id,
                    SceneDB.scheduled_absolute_week.between(start_absolute_week, end_absolute_week),
                    SceneDB.status == 'scheduled'
                )\
                .options(selectinload(SceneCastDB.scene))\
                .all()

            for entry in cast_entries:
                bookings_by_absolute_week[entry.scene.scheduled_absolute_week].append(entry.scene.to_dataclass(Scene))
            
            return bookings_by_absolute_week
        
    def get_talent_tours_for_year(self, talent_id: int, year: int) -> List[Tour]:
        """Fetches all tours for a talent that are active at any point during a given year."""
        start_abs_week = time_utils.to_absolute(year, 1)
        end_abs_week = time_utils.to_absolute(year, 52)

        with self.session_factory() as session:
            # A tour is relevant if its date range overlaps with the year's date range.
            tours_db = session.query(TourDB).filter(
                TourDB.talent_id == talent_id,
                TourDB.status != 'completed',
                # Tour starts before or during the year
                TourDB.start_absolute_week <= end_abs_week,
                # Tour ends on or after the start of the year
                (TourDB.start_absolute_week + TourDB.duration_weeks) >= start_abs_week
            ).all()
            
            return [t.to_dataclass(Tour) for t in tours_db]
        
    def get_recent_workload_counts(self, talent_ids: List[int], current_absolute_week: int, lookback_weeks: int = 4) -> Dict[int, int]:
        """
        Returns a dictionary {talent_id: count} of scenes in the last N weeks.
        """
        if not talent_ids:
            return {}

        cutoff_abs = current_absolute_week - lookback_weeks

        with self.session_factory() as session:
            results = (
                session.query(
                    SceneCastDB.talent_id,
                    func.count(SceneCastDB.id)
                )
                .join(SceneDB)
                .filter(
                    SceneCastDB.talent_id.in_(talent_ids),
                    SceneDB.status.in_(['scheduled', 'shot', 'completed', 'released']),
                    SceneDB.scheduled_absolute_week >= cutoff_abs,
                    SceneDB.scheduled_absolute_week < current_absolute_week
                )
                .group_by(SceneCastDB.talent_id)
                .all()
            )

            counts = {r[0]: r[1] for r in results}
            
            for t_id in talent_ids:
                if t_id not in counts:
                    counts[t_id] = 0
                    
            return counts
        
    def get_talent_schedule_status_for_year(self, talent_id: int, year: int) -> List[WeeklyStatusResult]:
        """
        Retrieves and calculates the status of every week in the year for the given talent.
        """
        start_absolute_week_of_year = time_utils.to_absolute(year, 1)
        end_absolute_week_of_year = time_utils.to_absolute(year, 52)
        bookings_by_absolute_week = self.get_talent_bookings_by_absolute_week(
            talent_id, start_absolute_week_of_year, end_absolute_week_of_year
        )
        tours = self.get_talent_tours_for_year(talent_id, year)
        
        tour_map = {}
        for tour in tours:
            for i in range(tour.duration_weeks):
                tour_abs_week = tour.start_absolute_week + i
                tour_year, tour_week_num = time_utils.from_absolute(tour_abs_week)
                if tour_year == year:
                    tour_map[tour_week_num] = tour

        talent_dc = self.query_service.get_talent_by_id(talent_id)
        if not talent_dc: return []

        results = []
        for week_num in range(1, 53):
            absolute_week = time_utils.to_absolute(year, week_num)
            bookings = bookings_by_absolute_week.get(absolute_week, [])
            tour = tour_map.get(week_num) # Tour map still uses week_num for year-based display
            
            result = self.status_calculator.calculate_week_status(
                talent_dc, absolute_week, bookings, tour
            )
            results.append(result)
            
        return results

    def get_eligible_talent_for_role(self, scene_id: int, vp_id: int, filters: Dict = None) -> List[TalentDB]:
        session = self.session_factory()
        try:
            scene_db = session.query(SceneDB).options(
                selectinload(SceneDB.virtual_performers),
                selectinload(SceneDB.cast),
                selectinload(SceneDB.action_segments).selectinload(ActionSegmentDB.slot_assignments),
                selectinload(SceneDB.bloc)
            ).get(scene_id)

            studio_state = session.query(StudioStateDB).get(1) # Assuming ID 1 is singleton
            current_policies = studio_state.studio_policies if studio_state else []

            if not scene_db: return []
            scene = self.query_service.get_scene_by_id(scene_id) # Scene dataclass
            
            vp = next((v for v in scene_db.virtual_performers if v.id == vp_id), None)
            if not vp: return []

            # --- Filter Logic Construction ---
            # Create a copy of user filters to safely modify with role requirements
            query_filters = filters.copy() if filters else {}

            # 1. Strict Gender Override: The Role determines the gender, not the user filter.
            query_filters['gender'] = vp.gender

            # 2. Strict Ethnicity Override: 
            # If the Role requires a specific ethnicity, it overrides user preference.
            # If the Role is "Any", we respect the user's filter (allows casting a specific ethnicity for an 'Any' role).
            if vp.ethnicity != "Any":
                query_filters['ethnicity'] = vp.ethnicity
                # Remove list-based 'ethnicities' if present so GameQueryService uses the strict 'ethnicity' key
                query_filters.pop('ethnicities', None)

            # 3. Contextual Cleanup: Remove filters irrelevant to the target gender
            if vp.gender == "Male":
                query_filters.pop('cup_sizes', None)
                query_filters.pop('cup_size', None)
            elif vp.gender == "Female":
                query_filters.pop('dick_size_min', None)
                query_filters.pop('dick_size_max', None)

            # --- Execute Database Query ---
            # Retrieve candidates matching the combined hard (Role) and soft (User) constraints
            filtered_candidates = self.query_service.get_filtered_talents(query_filters)
            candidate_ids = [t.id for t in filtered_candidates]
            
            if not candidate_ids:
                return []
            
            # Re-fetch in current session context
            potential_candidates_db = session.query(TalentDB).filter(TalentDB.id.in_(candidate_ids)).all()

            # --- Availability & Logic Checks ---
            # Pre-fetch weekly bookings for all candidates
            all_bookings = self._get_bookings_by_absolute_week(session, candidate_ids)
            
            scene_abs_week = scene.scheduled_absolute_week
            bookings_for_this_week = all_bookings.get(scene_abs_week, {})
            
            bloc_db = scene_db.bloc

            eligible_talents_db = []
            for talent_db in potential_candidates_db:
                bookings_before = all_bookings.get(scene_abs_week - 1, {}).get(talent_db.id, [])
                bookings_current = bookings_for_this_week.get(talent_db.id, [])
                bookings_after = all_bookings.get(scene_abs_week + 1, {}).get(talent_db.id, [])
                
                estimated_fatigue = self.shoot_results_calculator.estimate_fatigue_gain(talent_db, scene, vp_id)
                
                result = self.availability_checker.check(
                    talent_db, scene, vp_id, bloc_db, 
                    bookings_before, bookings_current, bookings_after, 
                    estimated_fatigue, studio_policies=current_policies
                )
                if result.is_available:
                    eligible_talents_db.append(talent_db)
                
            return sorted(eligible_talents_db, key=lambda t: t.alias)
        except Exception as e:
            logger.error(f"Error getting eligible talent for role {vp_id} in scene {scene_id}: {e}", exc_info=True)
            return []
        finally:
            session.close()
    
    def find_available_roles_for_talent(self, talent_id: int, studio_location: str, current_absolute_week: int) -> List[Dict]:
        with self.session_factory() as session:
            talent_db = session.query(TalentDB).options(selectinload(TalentDB.popularity_scores)).get(talent_id)
            if not talent_db: return []
            
            talent_dc_full = self.query_service.get_talent_by_id(talent_id)
            if not talent_dc_full: return []

            available_roles = []
            scenes_in_casting = session.query(SceneDB).options(
                selectinload(SceneDB.virtual_performers),
                selectinload(SceneDB.cast), 
                selectinload(SceneDB.action_segments).selectinload(ActionSegmentDB.slot_assignments),
                selectinload(SceneDB.bloc) # Crucial: Load bloc to get region_id without query
            ).filter(SceneDB.status == 'casting').all()

            studio_state = session.query(StudioStateDB).get(1)
            current_policies = studio_state.studio_policies if studio_state else []
            
            bloc_ids = {s.bloc_id for s in scenes_in_casting if s.bloc_id}
            blocs_by_id = {b.id: b for b in session.query(ShootingBlocDB).filter(ShootingBlocDB.id.in_(bloc_ids)).all()} if bloc_ids else {}
            
            all_bookings = self._get_bookings_by_absolute_week(session, [talent_id])
            
            # Get Existing Bloc Commitments for accurate travel pricing ---
            existing_bloc_ids = self.get_booked_bloc_ids(talent_id)

            for scene_db in scenes_in_casting:
                # Convert to dataclass locally to avoid new session query
                scene = scene_db.to_dataclass(Scene)
                # Manually populate location from the eager-loaded bloc
                if scene_db.bloc:
                    scene.location = scene_db.bloc.region_id
                else:
                    scene.location = studio_location
                if talent_id in {c.talent_id for c in scene_db.cast}: continue

                scene_abs_week = scene.scheduled_absolute_week
                bookings_before = all_bookings.get(scene_abs_week - 1, {}).get(talent_id, [])
                bookings_current = all_bookings.get(scene_abs_week, {}).get(talent_id, [])
                bookings_after = all_bookings.get(scene_abs_week + 1, {}).get(talent_id, [])

                uncast_vp_ids = {vp.id for vp in scene_db.virtual_performers} - {c.virtual_performer_id for c in scene_db.cast}
                
                for vp_db in scene_db.virtual_performers:
                    if vp_db.id not in uncast_vp_ids: continue
                    if vp_db.gender != talent_db.gender: continue
                    if vp_db.ethnicity != "Any" and not self.data_manager.is_ethnicity_match(talent_db.ethnicity, vp_db.ethnicity): continue
                    
                    bloc_db = blocs_by_id.get(scene.bloc_id)
                    estimated_fatigue = self.shoot_results_calculator.estimate_fatigue_gain(talent_db, scene, vp_db.id)
                    
                    result = self.availability_checker.check(
                        talent_db, scene, vp_db.id, bloc_db,
                        bookings_before, bookings_current, bookings_after,
                        estimated_fatigue, studio_policies=current_policies
                    )

                    talent_effective_location = self.location_service.get_effective_location_at_date(
                        talent_id, scene.scheduled_absolute_week
                    )
                    
                    # Pass existing blocs to calculator so roles in blocs we are already committed to show $0 travel
                    cost_breakdown = self.demand_calculator.calculate_total_demand(
                        talent_dc_full, scene, vp_db.id, talent_effective_location,
                        current_absolute_week, existing_bloc_ids
                    )

                    role_info = {
                        'scene_id': scene_db.id, 'scene_title': scene_db.title,
                        'bloc_id': scene_db.bloc_id,
                        'scheduled_absolute_week': scene.scheduled_absolute_week,
                        'virtual_performer_id': vp_db.id, 'vp_name': vp_db.name,
                        'cost': cost_breakdown['total_cost'], 
                        'base_cost': cost_breakdown['base_cost'], 
                        'travel_fee': cost_breakdown['travel_fee'],
                        'rush_fee': cost_breakdown['rush_fee'],
                        'tags': self._get_role_tags_for_display(scene, vp_db.id),
                        'is_available': result.is_available, 'refusal_reason': result.reason
                    }
                    available_roles.append(role_info)
            return available_roles

    def get_role_details_for_ui(self, scene_id: int, vp_id: int) -> Dict:
        session = self.session_factory()
        try:
            scene_db = session.query(SceneDB).options(
                selectinload(SceneDB.virtual_performers),
                selectinload(SceneDB.action_segments).selectinload(ActionSegmentDB.slot_assignments)
            ).get(scene_id)
            if not scene_db:
                return {}
            
            scene = scene_db.to_dataclass(Scene)
            vp = next((v for v in scene.virtual_performers if v.id == vp_id), None)
            if not vp:
                return {}

            physical_tags = [tag for tag, vps in scene.assigned_tags.items() if vp_id in vps]

            details = {
                'gender': vp.gender,
                'ethnicity': vp.ethnicity,
                'is_protagonist': vp_id in scene.protagonist_vp_ids,
                'disposition': vp.disposition,
                'physical_tags': sorted(physical_tags),
                'action_roles': self._get_role_tags_for_display(scene, vp_id)
            }
            return details
        except Exception as e:
            logger.error(f"Error getting role details for {vp_id} in scene {scene_id}: {e}", exc_info=True)
            return {}
        finally:
            session.close()