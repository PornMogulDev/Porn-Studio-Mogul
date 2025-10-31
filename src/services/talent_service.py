import logging
from itertools import combinations
from sqlalchemy import tuple_
from sqlalchemy.orm import joinedload, selectinload
from typing import Dict, List, Optional, Tuple

from data.game_state import Talent, Scene
from data.data_manager import DataManager
from services.service_config import SceneCalculationConfig
from database.db_models import (TalentDB, TalentPopularityDB, TalentChemistryDB,
                                SceneDB, SceneCastDB, GameInfoDB)

logger = logging.getLogger(__name__)

class TalentService:
    def __init__(self, db_session, data_manager: DataManager, config: SceneCalculationConfig):
        self.session = db_session
        self.data_manager = data_manager
        self.config = config

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
        Can operate within a larger transaction if commit=False.
        """
        if len(cast_talents) < 2:
            return

        # Optimization: Fetch all existing chemistry pairs for the cast in one query
        all_pairs = [tuple(sorted((t1.id, t2.id))) for t1, t2 in combinations(cast_talents, 2)]
        existing_pairs_query = self.session.query(TalentChemistryDB.talent_a_id, TalentChemistryDB.talent_b_id).filter(
            tuple_(TalentChemistryDB.talent_a_id, TalentChemistryDB.talent_b_id).in_(all_pairs)
        )
        existing_pairs = {tuple(sorted(pair)) for pair in existing_pairs_query.all()}

        new_chems_added = False
        for t1, t2 in combinations(cast_talents, 2):
            # Ensure consistent key order
            id1, id2 = sorted((t1.id, t2.id))
            if (id1, id2) in existing_pairs:
                continue

            initial_score = 0  # Future: Add logic for initial score based on interaction
            new_chem = TalentChemistryDB(talent_a_id=id1, talent_b_id=id2, chemistry_score=initial_score)
            self.session.add(new_chem)
            new_chems_added = True
        
        if commit and new_chems_added:
            try:
                self.session.commit()
            except Exception as e:
                logger.error(f"Failed to create new chemistry: {e}", exc_info=True)
                self.session.rollback()

    def recalculate_talent_age_affinities(self, talent: Talent) -> Dict:
        """Recalculates affinities affected by age."""
        new_affinities = talent.tag_affinities.copy()
        rules = self.config.age_based_affinity_rules  # This method can stay as it relates to general talent state
        for rule in rules:
            tag_name = rule.get('tag')
            if talent.age >= rule.get('min_age') and talent.age <= rule.get('max_age'):
                new_affinities[tag_name] = rule.get('affinity_score', 0)
        return new_affinities

    def update_popularity_from_scene(self, scene_id: int, commit: bool = False):
        """
        Updates the popularity for all cast members of a released scene.
        Can operate within a larger transaction if commit=False.
        """
        scene_db = self.session.query(SceneDB).options(
            selectinload(SceneDB.cast)
        ).get(scene_id)
        
        if not (scene_db and scene_db.viewer_group_interest):
            return

        talent_ids = [c.talent_id for c in scene_db.cast]
        if not talent_ids:
            return
        
        # Optimization: Eager load popularity scores to avoid N+1 queries
        talents = self.session.query(TalentDB).options(
            selectinload(TalentDB.popularity_scores)
        ).filter(TalentDB.id.in_(talent_ids)).all()
        
        talent_map = {t.id: t for t in talents}
        viewer_interest = scene_db.viewer_group_interest
        
        for talent_id in talent_ids:
            talent_db = talent_map.get(talent_id)
            if not talent_db:
                continue
            
            pop_map = {p.market_group_name: p for p in talent_db.popularity_scores}
            
            for group_name, interest_score in viewer_interest.items():
                base_gain = interest_score * self.config.popularity_gain_scalar
                
                if group_name in pop_map:
                    pop_entry = pop_map[group_name]
                    # Apply diminishing returns for popularity gain
                    current_pop = pop_entry.score
                    diminishing_factor = 1 - (current_pop / 100.0) ** 1.5
                    actual_gain = base_gain * diminishing_factor
                    pop_entry.score = min(100.0, current_pop + actual_gain)
                else:
                    new_pop_entry = TalentPopularityDB(
                        talent_id=talent_id,
                        market_group_name=group_name,
                        score=min(100.0, base_gain) # First gain has no diminishing returns
                    )
                    self.session.add(new_pop_entry)

        if commit:
            try:
                self.session.commit()
            except Exception as e:
                logger.error(f"Failed to update talent popularity for scene {scene_id}: {e}", exc_info=True)
                self.session.rollback()