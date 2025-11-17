import logging
from typing import Dict, List, Optional
from sqlalchemy.orm import Session, selectinload

from data.game_state import Tour, Talent
from database.db_models import TourDB, TalentDB

logger = logging.getLogger(__name__)

class TalentLocationService:
    """
    A dedicated, read-only service for determining a talent's effective
    location at any given point in time (past, present, or future).
    It acts as a "location oracle" for the rest of the application.
    """
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def _find_active_tour_at_date(self, session: Session, talent_id: int, week: int, year: int) -> Optional[Tour]:
        """
        Internal helper to find if a talent has a planned or active tour
        covering a specific future week/year for a single talent.
        """
        # Find tours that could potentially overlap the target date.
        # Pre-filter: the tour must start on or before the target date.
        potential_tours = session.query(TourDB).filter(
            TourDB.talent_id == talent_id,
            TourDB.status.in_(['planned', 'active']),
            (TourDB.start_year < year) | ((TourDB.start_year == year) & (TourDB.start_week <= week))
        ).all()

        for tour_db in potential_tours:
            # Calculate the tour's end date in Python to handle year wrapping.
            # A tour of D weeks starting in W ends AT THE START of week W+D.
            # So it covers weeks W, W+1, ..., W+D-1.
            end_week = tour_db.start_week + tour_db.duration_weeks - 1
            end_year = tour_db.start_year
            if end_week > 52:
                end_year += (end_week - 1) // 52
                end_week = (end_week - 1) % 52 + 1

            # Check if the target date is within the tour's [start, end] range
            is_after_start = (year > tour_db.start_year) or (year == tour_db.start_year and week >= tour_db.start_week)
            is_before_end = (year < end_year) or (year == end_year and week <= end_week)

            if is_after_start and is_before_end:
                return tour_db.to_dataclass(Tour)
        return None

    def get_effective_location_at_date(self, talent_id: int, week: int, year: int) -> str:
        """
        Gets the authoritative location for a single talent on a given date.
        This will be their tour destination if on tour, otherwise their home base.
        """
        with self.session_factory() as session:
            active_tour = self._find_active_tour_at_date(session, talent_id, week, year)
            if active_tour:
                return active_tour.destination_location
            
            # .scalar() is slightly more efficient if we only need one column
            talent_location = session.query(TalentDB.base_location).filter_by(id=talent_id).scalar()
            return talent_location or 'Unknown'

    def get_effective_locations_for_multiple_talents(self, talent_ids: List[int], week: int, year: int) -> Dict[int, str]:
        """
        Efficiently gets the authoritative location for a list of talents on a given date.
        """
        if not talent_ids:
            return {}
            
        with self.session_factory() as session:
            # 1. Get base locations for everyone as a default
            talents_db = session.query(TalentDB.id, TalentDB.base_location).filter(TalentDB.id.in_(talent_ids)).all()
            locations = {t.id: t.base_location for t in talents_db}

            # 2. Find all potentially relevant tours in a single query
            potential_tours = session.query(TourDB).filter(
                TourDB.talent_id.in_(talent_ids),
                TourDB.status.in_(['planned', 'active']),
                (TourDB.start_year < year) | ((TourDB.start_year == year) & (TourDB.start_week <= week))
            ).all()

            # 3. In memory, check which tours are active and override the base location
            for tour_db in potential_tours:
                end_week = tour_db.start_week + tour_db.duration_weeks - 1
                end_year = tour_db.start_year
                if end_week > 52:
                    end_year += (end_week - 1) // 52
                    end_week = (end_week - 1) % 52 + 1

                is_after_start = (year > tour_db.start_year) or (year == tour_db.start_year and week >= tour_db.start_week)
                is_before_end = (year < end_year) or (year == end_year and week <= end_week)

                if is_after_start and is_before_end:
                    locations[tour_db.talent_id] = tour_db.destination_location
            
            return locations