import logging
from itertools import combinations
from sqlalchemy import tuple_
from sqlalchemy.orm import selectinload, Session
from typing import List, Set

from core.game_signals import GameSignals
from data.game_state import Talent
from services.models.configs import SceneCalculationConfig
from database.db_models import SceneDB,TalentDB, TalentPopularityDB, TalentChemistryDB
from services.calculation.talent_affinity_calculator import TalentAffinityCalculator

logger = logging.getLogger(__name__)

class TalentCommandService:
    """Manages all state changes (writes/commands) related to talents."""

    def __init__(self, signals: GameSignals, config: SceneCalculationConfig, talent_affinity_calculator: TalentAffinityCalculator):
        self.signals = signals
        self.config = config
        self.talent_affinity_calculator = talent_affinity_calculator

    def discover_and_create_chemistry(self, session: Session, cast_talents: List[Talent]):
        """Checks for new chemistry pairs during a scene shot and creates them in the database.
        Called from SceneProcessingService"""
        if len(cast_talents) < 2:
            return

        all_possible_pairs = [tuple(sorted((t1.id, t2.id))) for t1, t2 in combinations(cast_talents, 2)]
        
        if not all_possible_pairs:
            return

        existing_pairs_query = session.query(TalentChemistryDB.talent_a_id, TalentChemistryDB.talent_b_id).filter(
            tuple_(TalentChemistryDB.talent_a_id, TalentChemistryDB.talent_b_id).in_(all_possible_pairs)
        )
        existing_pairs = {tuple(sorted(pair)) for pair in existing_pairs_query.all()}

        for t1, t2 in combinations(cast_talents, 2):
            id1, id2 = sorted((t1.id, t2.id))
            if (id1, id2) in existing_pairs:
                continue

            initial_score = 0
            new_chem = TalentChemistryDB(talent_a_id=id1, talent_b_id=id2, chemistry_score=initial_score)
            session.add(new_chem)

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

    def update_popularity_from_scene(self, session: Session, scene_id: int):
        """Updates the popularity for all cast members of a released scene.
        Called from SceneCommandService."""
        scene_db = session.query(SceneDB).options(selectinload(SceneDB.cast)).get(scene_id)
        if not (scene_db and scene_db.viewer_group_interest): return
        
        talent_ids = [c.talent_id for c in scene_db.cast]
        if not talent_ids: return

        talents = session.query(TalentDB).options(selectinload(TalentDB.popularity_scores)).filter(TalentDB.id.in_(talent_ids)).all()
        
        for talent_db in talents:
            pop_map = {p.market_group_name: p for p in talent_db.popularity_scores}
            for group_name, interest_score in scene_db.viewer_group_interest.items():
                if group_name in pop_map:
                    pop_entry = pop_map[group_name]
                    pop_entry.score = self._calculate_new_popularity_score(pop_entry.score, interest_score)
                else:
                    initial_score = self._calculate_new_popularity_score(0.0, interest_score)
                    new_pop_entry = TalentPopularityDB(talent_id=talent_db.id, market_group_name=group_name, score=initial_score)
                    session.add(new_pop_entry)

    def _apply_popularity_decay(self, talent: TalentDB, decay_rate: float):
        """Applies a weekly decay to a talent's popularity scores."""
        for pop_entry in talent.popularity_scores:
            pop_entry.score *= decay_rate

    def _update_fatigue_status(self, talent: TalentDB, worked_talent_ids: Set[int]):
        """Checks and resets a talent's fatigue if the recovery period has passed."""
        # 1. Apply Passive Decay to everyone
        talent.fatigue = max(0, talent.fatigue - self.config.fatigue_passive_decay_rate)
    
        # 2. Apply Active Recovery Bonus only to those who rested
        if talent.id not in worked_talent_ids:
            stamina_bonus = (talent.stamina / 100.0) * self.config.fatigue_stamina_recovery_modifier
            recovery_amount = self.config.fatigue_active_recovery_bonus * (1 + stamina_bonus)
            talent.fatigue = max(0, int(talent.fatigue - recovery_amount))

    def _apply_new_year_updates(self, talent: TalentDB):
        """Applies annual updates to a talent, such as aging and recalculating affinities."""
        talent.age += 1
        talent_obj = talent.to_dataclass(Talent)
        new_affinities = self.talent_affinity_calculator.recalculate_talent_age_affinities(talent_obj)
        talent.tag_affinities = new_affinities
    
    def process_weekly_updates(self, session: Session, new_year: bool, worked_talent_ids: Set[int]) -> bool:
        """Processes all weekly changes for talents.
        Called from TimeService."""
        talents_to_update = session.query(TalentDB).options(
            selectinload(TalentDB.popularity_scores),
            selectinload(TalentDB.chemistry_a).joinedload(TalentChemistryDB.talent_b),
            selectinload(TalentDB.chemistry_b).joinedload(TalentChemistryDB.talent_a)
        ).all()
        if not talents_to_update: return False

        decay_rate = 1.0 - self.config.popularity_gain_scalar
        for talent in talents_to_update:
            self._apply_popularity_decay(talent, decay_rate)
            self._update_fatigue_status(talent, worked_talent_ids)
            
            if new_year:
                self._apply_new_year_updates(talent)
        
        return True