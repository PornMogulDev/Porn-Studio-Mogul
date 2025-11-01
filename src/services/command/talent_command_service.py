import logging
from itertools import combinations
from sqlalchemy import tuple_
from sqlalchemy.orm import selectinload
from typing import List

from core.game_signals import GameSignals
from data.game_state import Talent
from services.models.configs import SceneCalculationConfig
from database.db_models import SceneDB,TalentDB, TalentPopularityDB, TalentChemistryDB
from services.utils.talent_logic_helper import TalentLogicHelper

logger = logging.getLogger(__name__)

class TalentCommandService:
    """Manages all state changes (writes/commands) related to talents."""

    def __init__(self, db_session, signals: GameSignals, config: SceneCalculationConfig, talent_logic_helper: TalentLogicHelper):
        self.session = db_session
        self.signals = signals
        self.config = config
        self.talent_logic_helper = talent_logic_helper

    def discover_and_create_chemistry(self, cast_talents: List[Talent], commit: bool = False):
        """Checks for new chemistry pairs and creates them in the database."""
        if len(cast_talents) < 2:
            return

        all_possible_pairs = [tuple(sorted((t1.id, t2.id))) for t1, t2 in combinations(cast_talents, 2)]
        
        if not all_possible_pairs:
            return

        existing_pairs_query = self.session.query(TalentChemistryDB.talent_a_id, TalentChemistryDB.talent_b_id).filter(
            tuple_(TalentChemistryDB.talent_a_id, TalentChemistryDB.talent_b_id).in_(all_possible_pairs)
        )
        existing_pairs = {tuple(sorted(pair)) for pair in existing_pairs_query.all()}

        new_chems_added = False
        for t1, t2 in combinations(cast_talents, 2):
            id1, id2 = sorted((t1.id, t2.id))
            if (id1, id2) in existing_pairs:
                continue

            initial_score = 0
            new_chem = TalentChemistryDB(talent_a_id=id1, talent_b_id=id2, chemistry_score=initial_score)
            self.session.add(new_chem)
            new_chems_added = True
        
        if commit and new_chems_added:
            try:
                self.session.commit()
            except Exception as e:
                logger.error(f"Failed to create new chemistry: {e}", exc_info=True)
                self.session.rollback()

    def _calculate_new_popularity_score(self, current_pop: float, interest_score: float) -> float:
        """Calculates the popularity gain with diminishing returns."""
        base_gain = interest_score * self.config.popularity_gain_scalar
        if current_pop > 0:
            diminishing_factor = 1 - (current_pop / 100.0) ** 1.5
            actual_gain = base_gain * max(0.0, diminishing_factor)
            new_pop = current_pop + actual_gain
        else:
            new_pop = base_gain
        return min(100.0, new_pop)

    def update_popularity_from_scene(self, scene_id: int, commit: bool = False):
        """Updates the popularity for all cast members of a released scene."""
        # Note: This method queries the DB, which is acceptable for a command
        # service as it needs the current state to calculate the new state.
        scene_db = self.session.query(SceneDB).options(selectinload(SceneDB.cast)).get(scene_id)
        if not (scene_db and scene_db.viewer_group_interest): return
        
        talent_ids = [c.talent_id for c in scene_db.cast]
        if not talent_ids: return

        talents = self.session.query(TalentDB).options(selectinload(TalentDB.popularity_scores)).filter(TalentDB.id.in_(talent_ids)).all()
        
        for talent_db in talents:
            pop_map = {p.market_group_name: p for p in talent_db.popularity_scores}
            for group_name, interest_score in scene_db.viewer_group_interest.items():
                if group_name in pop_map:
                    pop_entry = pop_map[group_name]
                    pop_entry.score = self._calculate_new_popularity_score(pop_entry.score, interest_score)
                else:
                    initial_score = self._calculate_new_popularity_score(0.0, interest_score)
                    new_pop_entry = TalentPopularityDB(talent_id=talent_db.id, market_group_name=group_name, score=initial_score)
                    self.session.add(new_pop_entry)

        if commit:
            try:
                self.session.commit()
            except Exception as e:
                logger.error(f"Failed to update talent popularity for scene {scene_id}: {e}", exc_info=True)
                self.session.rollback()

    def process_weekly_updates(self, current_date_val: int, new_year: bool) -> bool:
        """Processes all weekly changes for talents."""
        talents_to_update = self.session.query(TalentDB).options(selectinload(TalentDB.popularity_scores)).all()
        if not talents_to_update: return False

        decay_rate = 1.0 - self.config.popularity_gain_scalar # Corrected decay
        for talent in talents_to_update:
            for pop_entry in talent.popularity_scores:
                pop_entry.score *= decay_rate
            
            if talent.fatigue > 0:
                fatigue_end_val = talent.fatigue_end_year * 52 + talent.fatigue_end_week
                if current_date_val >= fatigue_end_val:
                    talent.fatigue, talent.fatigue_end_week, talent.fatigue_end_year = 0, 0, 0
            
            if new_year:
                talent.age += 1
                talent_obj = talent.to_dataclass(Talent)
                new_affinities = self.talent_logic_helper.recalculate_talent_age_affinities(talent_obj)
                talent.tag_affinities = new_affinities
        
        return True