import logging
from itertools import combinations
from sqlalchemy import tuple_
from sqlalchemy.orm import joinedload, selectinload
from typing import Dict, List, Optional, Tuple

from data.game_state import Talent, Scene
from data.data_manager import DataManager
from services.models.configs import SceneCalculationConfig
from database.db_models import (TalentDB, TalentPopularityDB, TalentChemistryDB,
                                SceneDB, SceneCastDB, GameInfoDB)
from services.utils.talent_logic_helper import TalentLogicHelper

logger = logging.getLogger(__name__)

class TalentService:
    def __init__(self, db_session, data_manager: DataManager, config: SceneCalculationConfig, talent_logic_helper: TalentLogicHelper):
        self.session = db_session
        self.data_manager = data_manager
        self.config = config
        self.talent_logic_helper = talent_logic_helper

    def get_filtered_talents(self, all_filters: dict) -> List[TalentDB]:
        query = self.session.query(TalentDB).options(selectinload(TalentDB.popularity_scores))
        
        # This logic remains the same as it's for UI filtering
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
        Fetches a single talent by their ID and converts it to a dataclass.
        Eager-loads popularity and chemistry for full data hydration.
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

    def discover_and_create_chemistry(self, cast_talents: List[Talent], commit: bool = False):
        """
        Checks for new chemistry pairs and creates them in the database.
        (Wrapper around logic methods).
        """
        if len(cast_talents) < 2:
            return

        talent_ids = [t.id for t in cast_talents]
        
        # 1. Fetch existing pairs for the current cast
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

            # 2. Persist new pairs
            initial_score = 0  # Logic for initial score is externalized or set to 0 here
            new_chem = TalentChemistryDB(talent_a_id=id1, talent_b_id=id2, chemistry_score=initial_score)
            self.session.add(new_chem)
            new_chems_added = True
        
        if commit and new_chems_added:
            try:
                self.session.commit()
            except Exception as e:
                logger.error(f"Failed to create new chemistry: {e}", exc_info=True)
                self.session.rollback()

    def get_talent_chemistry(self, talent_id: int) -> Dict[int, Dict]:
        """
        Fetches all chemistry relationships for a given talent.

        Args:
            talent_id: The ID of the talent to look up.

        Returns:
            A dictionary mapping the other talent's ID to a dict containing
            their alias and the chemistry score. e.g., {102: {'alias': 'Jane Doe', 'score': 15}}
        """
        from sqlalchemy import or_

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
    
    def _calculate_new_popularity_score(self, current_pop: float, interest_score: float) -> float:
        """
        [UNIT TESTABLE LOGIC] Calculates the popularity gain with diminishing returns.
        """
        base_gain = interest_score * self.config.popularity_gain_scalar
        
        # Apply diminishing returns only if current pop > 0
        if current_pop > 0:
            # 1.5 exponent provides a reasonable curve
            diminishing_factor = 1 - (current_pop / 100.0) ** 1.5 
            actual_gain = base_gain * max(0.0, diminishing_factor) # Ensure gain is non-negative
            new_pop = current_pop + actual_gain
        else:
            new_pop = base_gain
            
        return min(100.0, new_pop)

    def update_popularity_from_scene(self, scene_id: int, commit: bool = False):
        """
        Updates the popularity for all cast members of a released scene.
        Focuses on DB orchestration and uses the dedicated calculation helper.
        """
        scene_db = self.session.query(SceneDB).options(
            selectinload(SceneDB.cast)
        ).get(scene_id)
        
        if not (scene_db and scene_db.viewer_group_interest):
            return

        talent_ids = [c.talent_id for c in scene_db.cast]
        if not talent_ids:
            return
        
        talents = self.session.query(TalentDB).options(
            selectinload(TalentDB.popularity_scores)
        ).filter(TalentDB.id.in_(talent_ids)).all()
        
        talent_map = {t.id: t for t in talents}
        viewer_interest = scene_db.viewer_group_interest
        
        for talent_db in talents:
            pop_map = {p.market_group_name: p for p in talent_db.popularity_scores}
            
            for group_name, interest_score in viewer_interest.items():
                
                if group_name in pop_map:
                    pop_entry = pop_map[group_name]
                    current_pop = pop_entry.score
                    pop_entry.score = self._calculate_new_popularity_score(current_pop, interest_score)
                else:
                    # New popularity entry (initial score is derived directly from calculation)
                    initial_score = self._calculate_new_popularity_score(0.0, interest_score)
                    new_pop_entry = TalentPopularityDB(
                        talent_id=talent_db.id,
                        market_group_name=group_name,
                        score=initial_score
                    )
                    self.session.add(new_pop_entry)

        if commit:
            try:
                self.session.commit()
            except Exception as e:
                logger.error(f"Failed to update talent popularity for scene {scene_id}: {e}", exc_info=True)
                self.session.rollback()

    def process_weekly_updates(self, current_date_val: int, new_year: bool) -> bool:
        """
        Processes all weekly changes for talents: popularity decay, fatigue recovery, and aging.
        Returns True if any talent data was changed.
        """
        talents_to_update = self.session.query(TalentDB).options(
            selectinload(TalentDB.popularity_scores)
        ).all()
        if not talents_to_update:
            return False

        # --- Popularity Decay ---
        decay_rate = self.config.popularity_gain_scalar
        for talent in talents_to_update:
            for pop_entry in talent.popularity_scores:
                pop_entry.score *= decay_rate
            
            # --- Fatigue Recovery ---
            if talent.fatigue > 0:
                fatigue_end_val = talent.fatigue_end_year * 52 + talent.fatigue_end_week
                if current_date_val >= fatigue_end_val:
                    talent.fatigue = 0
                    talent.fatigue_end_week = 0
                    talent.fatigue_end_year = 0
            
            # --- Aging ---
            if new_year:
                talent.age += 1
                talent_obj = talent.to_dataclass(Talent) 
                new_affinities = self.talent_logic_helper.recalculate_talent_age_affinities(talent_obj)
                talent.tag_affinities = new_affinities
        
        return True