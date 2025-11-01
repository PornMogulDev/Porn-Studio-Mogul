import logging
from typing import List, Dict, Optional

from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import or_

from data.game_state import Talent
from database.db_models import TalentDB, TalentChemistryDB

logger = logging.getLogger(__name__)

class GameQueryService:
    """A unified, read-only service for fetching game data for the UI."""

    def __init__(self, db_session):
        self.session = db_session

    # --- Talent Query Methods ---

    def get_filtered_talents(self, all_filters: dict) -> List[TalentDB]:
        """Fetches a list of TalentDB objects based on UI filters."""
        query = self.session.query(TalentDB).options(selectinload(TalentDB.popularity_scores))
        
        if name_filter := all_filters.get('name'):
            query = query.filter(TalentDB.alias.ilike(f"%{name_filter}%"))
        if gender_filter := all_filters.get('gender'):
            if gender_filter != 'Any':
                query = query.filter(TalentDB.gender == gender_filter)
        if ethnicity_filter := all_filters.get('ethnicity'):
            if ethnicity_filter != 'Any':
                query = query.filter(TalentDB.ethnicity == ethnicity_filter)
        if boob_cup_filter := all_filters.get('boob_cup'):
            if boob_cup_filter != 'Any':
                query = query.filter(TalentDB.boob_cup == boob_cup_filter)

        return query.order_by(TalentDB.alias).all()

    def get_talent_by_id(self, talent_id: int) -> Optional[Talent]:
        """
        Fetches a single talent by ID and converts it to a fully hydrated dataclass.
        """
        if talent_id is None:
            return None
        t = self.session.query(TalentDB).options(
            selectinload(TalentDB.popularity_scores),
            selectinload(TalentDB.chemistry_a).joinedload(TalentChemistryDB.talent_b),
            selectinload(TalentDB.chemistry_b).joinedload(TalentChemistryDB.talent_a)
        ).get(talent_id)
        if t:
            return t.to_dataclass(Talent)
        return None

    def get_talent_chemistry(self, talent_id: int) -> Dict[int, Dict]:
        """Fetches all chemistry relationships for a given talent."""
        chemistry_relations_db = self.session.query(TalentChemistryDB).options(
            joinedload(TalentChemistryDB.talent_a),
            joinedload(TalentChemistryDB.talent_b)
        ).filter(
            or_(TalentChemistryDB.talent_a_id == talent_id, TalentChemistryDB.talent_b_id == talent_id)
        ).all()

        results = {}
        for rel in chemistry_relations_db:
            other_talent = rel.talent_b if rel.talent_a_id == talent_id else rel.talent_a
            results[other_talent.id] = {'alias': other_talent.alias, 'score': rel.chemistry_score}
        return results