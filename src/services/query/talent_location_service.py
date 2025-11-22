import logging
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from data.game_state import Tour
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

    def _find_active_tour_at_date(self, session: Session, talent_id: int, absolute_week: int) -> Optional[Tour]:
        """
        Internal helper to find if a talent has a planned or active tour
        covering a specific absolute_week for a single talent.
        """
        potential_tours = session.query(TourDB).filter(
            TourDB.talent_id == talent_id,
            TourDB.status.in_(['planned', 'active']),
            TourDB.start_absolute_week <= absolute_week
        ).all()

        for tour_db in potential_tours:
            end_absolute_week = tour_db.start_absolute_week + tour_db.duration_weeks
            if tour_db.start_absolute_week <= absolute_week < end_absolute_week:
                return tour_db.to_dataclass(Tour)
        return None

    def get_effective_location_at_date(self, talent_id: int, absolute_week: int) -> str:
        """
        Gets the authoritative location for a single talent on a given date.
        This will be their tour destination if on tour, otherwise their home base.
        """
        with self.session_factory() as session:
            active_tour = self._find_active_tour_at_date(session, talent_id, absolute_week)
            if active_tour:
                return active_tour.destination_location
            
            talent_location = session.query(TalentDB.base_location).filter_by(id=talent_id).scalar()
            return talent_location or 'Unknown'

    def get_effective_locations_for_multiple_talents(self, talent_ids: List[int], absolute_week: int) -> Dict[int, str]:
        """
        Efficiently gets the authoritative location for a list of talents on a given date.
        """
        if not talent_ids:
            return {}
            
        with self.session_factory() as session:
            talents_db = session.query(TalentDB.id, TalentDB.base_location).filter(TalentDB.id.in_(talent_ids)).all()
            locations = {t.id: t.base_location for t in talents_db}

            potential_tours = session.query(TourDB).filter(
                TourDB.talent_id.in_(talent_ids),
                TourDB.status.in_(['planned', 'active']),
                TourDB.start_absolute_week <= absolute_week
            ).all()

            for tour_db in potential_tours:
                end_absolute_week = tour_db.start_absolute_week + tour_db.duration_weeks
                if tour_db.start_absolute_week <= absolute_week < end_absolute_week:
                    locations[tour_db.talent_id] = tour_db.destination_location
            
            return locations