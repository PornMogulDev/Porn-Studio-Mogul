import numpy as np
import random
from typing import Dict, Optional, List, Set
from collections import defaultdict
from itertools import combinations
from sqlalchemy.orm import selectinload

from data.game_state import Talent, Scene, ActionSegment
from services.market_service import MarketService
from data.data_manager import DataManager
from database.db_models import (
    TalentDB, SceneDB, VirtualPerformerDB, ActionSegmentDB, TalentChemistryDB,
    ShootingBlocDB, GoToListAssignmentDB, TalentPopularityDB
)

class TalentService:
    def __init__(self, db_session, data_manager: DataManager, market_service: MarketService):
        self.session = db_session
        self.data_manager = data_manager
        self.market_service = market_service
    def get_talent_by_id(self, talent_id: int) -> Optional[Talent]:
        """Fetches a single talent from the DB and converts it to a dataclass."""
        talent_db = self.session.query(TalentDB).get(talent_id)
        return talent_db.to_dataclass(Talent) if talent_db else None

    def get_talent_chemistry(self, talent_id: int) -> List[Dict]:
        """
        Fetches all chemistry relationships for a given talent for UI display.
        Returns a list of dictionaries with the other talent's ID, alias, and the score.
        """
        results = []
        
        # Query where the talent is talent_a
        query_a = self.session.query(TalentChemistryDB, TalentDB.id, TalentDB.alias)\
            .join(TalentDB, TalentChemistryDB.talent_b_id == TalentDB.id)\
            .filter(TalentChemistryDB.talent_a_id == talent_id)
            
        for chem, other_id, other_alias in query_a.all():
            results.append({
                "other_talent_id": other_id,
                "other_talent_alias": other_alias,
                "score": chem.chemistry_score
            })

        # Query where the talent is talent_b
        query_b = self.session.query(TalentChemistryDB, TalentDB.id, TalentDB.alias)\
            .join(TalentDB, TalentChemistryDB.talent_a_id == TalentDB.id)\
            .filter(TalentChemistryDB.talent_b_id == talent_id)

        for chem, other_id, other_alias in query_b.all():
            results.append({
                "other_talent_id": other_id,
                "other_talent_alias": other_alias,
                "score": chem.chemistry_score
            })
            
        return sorted(results, key=lambda x: x['other_talent_alias'])

    def get_filtered_talents(self, filters: dict) -> List[TalentDB]:
        """
        Builds and executes a dynamic query to fetch talents from the DB
        based on a dictionary of filter criteria.
        """
        query = self.session.query(TalentDB).options(selectinload(TalentDB.popularity_scores))

        # Go-To List only filter 
        if filters.get('go_to_list_only'):
            # Use distinct() in case a talent is in multiple categories
            query = query.join(GoToListAssignmentDB).distinct()

        # Go-To Category Filter
        category_id = filters.get('go_to_category_id', -1)
        if category_id != -1:
            query = query.join(GoToListAssignmentDB).filter(GoToListAssignmentDB.category_id == category_id)

        # Text filter
        if text := filters.get('text', '').strip():
            query = query.filter(TalentDB.alias.ilike(f'%{text}%'))
        
        # Age
        query = query.filter(TalentDB.age >= filters.get('age_min', 18))
        query = query.filter(TalentDB.age <= filters.get('age_max', 99))
        
        # Gender
        if (gender := filters.get('gender')) and gender != "Any":
                query = query.filter(TalentDB.gender == gender)

        # Ethnicity
        if ethnicities := filters.get('ethnicities'):
            if "Any" not in ethnicities:
                query = query.filter(TalentDB.ethnicity.in_(ethnicities))
        
        # Boob Cups
        if boob_cups := filters.get('boob_cups'):
            query = query.filter(TalentDB.boob_cup.in_(boob_cups))
            
        # Dick Size
        min_d, max_d = filters.get('dick_size_min', 0), filters.get('dick_size_max', 20)
        if min_d > 0 or max_d < 20:
            query = query.filter(TalentDB.dick_size != None)
            query = query.filter(TalentDB.dick_size.between(min_d, max_d))

        results = query.order_by(TalentDB.alias).all()
        return results

    def recalculate_talent_age_affinities(self, talent: Talent):
        gender_data = self.data_manager.affinity_data.get(talent.gender)
        new_affinities = {}
        if not gender_data: 
            return new_affinities
        
        raw_scores = {}
        for tag, data in gender_data.items():
            age_points, values = data.get("age_points", []), data.get("values", [])
            if age_points and values: 
                raw_scores[tag] = np.interp(talent.age, age_points, values)
        
        total_raw_score = sum(raw_scores.values())
        if total_raw_score == 0:
            for tag in gender_data: 
                new_affinities[tag] = 0
            return new_affinities
            
        for tag, raw_score in raw_scores.items():
            new_affinities[tag] = int(round((raw_score / total_raw_score) * 100))
            
        return new_affinities

    def calculate_skill_gain(self, talent: Talent, scene_runtime_minutes: int) -> tuple[float, float, float]:
        base_rate = self.data_manager.game_config.get("skill_gain_base_rate_per_minute", 0.02)
        ambition_scalar = self.data_manager.game_config.get("skill_gain_ambition_scalar", 0.015)
        cap = self.data_manager.game_config.get("skill_gain_diminishing_returns_cap", 100.0)
        median_ambition = self.data_manager.game_config.get("median_ambition", 5.5)
        ambition_modifier = 1.0 + ((talent.ambition - median_ambition) * ambition_scalar)
        base_gain = scene_runtime_minutes * base_rate * ambition_modifier
        
        def get_final_gain(current_skill_level: float) -> float:
            if current_skill_level >= cap: return 0.0
            return base_gain * (1.0 - (current_skill_level / cap))
            
        return get_final_gain(talent.performance), get_final_gain(talent.acting), get_final_gain(talent.stamina)

    def calculate_experience_gain(self, talent: Talent, scene_runtime_minutes: int) -> float:
        """Calculates the experience gain for a talent from participating in a scene."""
        base_gain = self.data_manager.game_config.get("experience_gain_base_rate", 0.5)
        runtime_multiplier = self.data_manager.game_config.get("experience_gain_runtime_multiplier", 0.1)
        cap = self.data_manager.game_config.get("maximum_experience_level", 100.0)

        # Calculate raw gain from this scene
        raw_gain = base_gain + (scene_runtime_minutes * runtime_multiplier)

        # Apply diminishing returns based on current experience
        if talent.experience >= cap:
            return 0.0
        
        # Experience gain has a simpler diminishing returns curve than skills
        final_gain = raw_gain * (1.0 - (talent.experience / cap))

        return final_gain

    def calculate_ds_skill_gain(self, talent: Talent, scene: Scene, disposition: str) -> tuple[float, float]:
        """Calculates Dom/Sub skill gains based on scene dynamic level and disposition."""
        base_rate = self.data_manager.game_config.get("skill_gain_base_rate_per_minute", 0.02)
        ambition_scalar = self.data_manager.game_config.get("skill_gain_ambition_scalar", 0.015)
        cap = self.data_manager.game_config.get("skill_gain_diminishing_returns_cap", 100.0)
        median_ambition = self.data_manager.game_config.get("median_ambition", 5.5)
        ambition_modifier = 1.0 + ((talent.ambition - median_ambition) * ambition_scalar)
        
        # D/S skill gain is heavily influenced by the scene's dynamic level
        ds_level_multiplier = scene.dom_sub_dynamic_level
        base_gain = scene.total_runtime_minutes * base_rate * ambition_modifier * ds_level_multiplier

        dom_bias, sub_bias = 0.25, 0.25 # Base gain for the off-disposition
        if disposition == "Dom":
            dom_bias = 1.0
        elif disposition == "Sub":
            sub_bias = 1.0
        elif disposition == "Switch":
            dom_bias, sub_bias = 0.75, 0.75

        def get_final_gain(current_skill_level: float, bias: float) -> float:
            if current_skill_level >= cap: return 0.0
            return base_gain * bias * (1.0 - (current_skill_level / cap))

        return get_final_gain(talent.dom_skill, dom_bias), get_final_gain(talent.sub_skill, sub_bias)

    def discover_and_create_chemistry(self, scene: Scene, cast_talents: Dict[int, Talent]):
        """
        Finds pairs of talent who worked together in action segments and creates
        a chemistry relationship if one doesn't already exist.
        Updates the in-memory talent objects with the new chemistry.
        """
        action_segments_for_calc = scene.get_expanded_action_segments(self.data_manager.tag_definitions)
        
        segment_pairs: Set[tuple[int, int]] = set()
        for segment in action_segments_for_calc:
            talent_in_segment = {scene.final_cast.get(str(sa.virtual_performer_id)) for sa in segment.slot_assignments}
            talent_in_segment.discard(None)
            
            if len(talent_in_segment) >= 2:
                for t1_id, t2_id in combinations(talent_in_segment, 2):
                    pair = tuple(sorted((t1_id, t2_id)))
                    segment_pairs.add(pair)
        
        if not segment_pairs:
            return

        existing_pairs_query = self.session.query(TalentChemistryDB.talent_a_id, TalentChemistryDB.talent_b_id)\
            .filter(TalentChemistryDB.talent_a_id.in_({p[0] for p in segment_pairs}))\
            .filter(TalentChemistryDB.talent_b_id.in_({p[1] for p in segment_pairs}))
        
        existing_pairs_db = {tuple(sorted((row.talent_a_id, row.talent_b_id))) for row in existing_pairs_query.all()}
        new_pairs = segment_pairs - existing_pairs_db

        if not new_pairs: return

        config = self.data_manager.game_config.get("chemistry_discovery_weights", {})
        outcomes = [int(k) for k in config.keys()]; weights = list(config.values())

        for t1_id, t2_id in new_pairs:
            score = random.choices(outcomes, weights=weights, k=1)[0]
            self.session.add(TalentChemistryDB(talent_a_id=t1_id, talent_b_id=t2_id, chemistry_score=score))
            if t1 := cast_talents.get(t1_id): t1.chemistry[t2_id] = score
            if t2 := cast_talents.get(t2_id): t2.chemistry[t1_id] = score

    def update_popularity_from_scene(self, scene_id: int):
        scene_db = self.session.query(SceneDB).get(scene_id)
        if not scene_db: return
        scene = scene_db.to_dataclass(Scene) # Use dataclass for easy data access
        
        gain_rate = self.data_manager.game_config.get("popularity_gain_base_rate", 2.0)
        max_pop = self.data_manager.game_config.get("max_popularity_per_group", 100.0)
        
        cast_talent_ids = list(scene.final_cast.values())
        if not cast_talent_ids: return
        
        cast_talents_db = self.session.query(TalentDB).filter(TalentDB.id.in_(cast_talent_ids)).all()
        if not cast_talents_db: return

        direct_gains = defaultdict(lambda: defaultdict(float))
        for group_name, interest_score in scene.viewer_group_interest.items():
            if interest_score > 0:
                gain = interest_score * gain_rate
                for talent_db in cast_talents_db: direct_gains[talent_db.id][group_name] += gain
        
        final_gains = defaultdict(lambda: defaultdict(float), {tid: gains.copy() for tid, gains in direct_gains.items()})
        resolved_market_groups = {g['name']: self.market_service.get_resolved_group_data(g['name']) for g in self.data_manager.market_data.get('viewer_groups', [])}
        
        for talent_id, gains_by_group in direct_gains.items():
            for source_group_name, gain_amount in gains_by_group.items():
                source_group_data = resolved_market_groups.get(source_group_name)
                if source_group_data:
                    spillover_rules = source_group_data.get('popularity_spillover', {})
                    for target_group_name, spill_rate in spillover_rules.items():
                        spillover_amount = gain_amount * spill_rate
                        final_gains[talent_id][target_group_name] += spillover_amount

        for talent_db in cast_talents_db:
            gains_by_group = final_gains.get(talent_db.id, {})
            for group_name, gain_amount in gains_by_group.items():
                pop_entry = self.session.query(TalentPopularityDB).filter_by(
                    talent_id=talent_db.id,
                    market_group_name=group_name
                ).one_or_none()

                if not pop_entry:
                    pop_entry = TalentPopularityDB(talent_id=talent_db.id, market_group_name=group_name, score=0.0)
                    self.session.add(pop_entry)
                
                pop_entry.score = min(max_pop, pop_entry.score + gain_amount)