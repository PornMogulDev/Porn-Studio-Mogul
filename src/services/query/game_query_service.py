import logging
from typing import List, Dict, Optional

from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import or_

from data.game_state import Talent, Scene, ShootingBloc
from database.db_models import (TalentDB, TalentChemistryDB, SceneDB, ShootingBlocDB, 
                                SceneCastDB, ActionSegmentDB, GoToListAssignmentDB,
                                GoToListCategoryDB )

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
    
    def get_all_talents_in_go_to_lists(self) -> List[Talent]:
        """Gets all unique talents present in any Go-To List category."""
        talents_db = self.session.query(TalentDB)\
            .join(GoToListAssignmentDB)\
            .distinct()\
            .order_by(TalentDB.alias).all()
        return [t.to_dataclass(Talent) for t in talents_db]
    
    # --- Go To List Queries ---

    def get_all_categories(self) -> List[Dict]:
        """Returns a list of all Go-To List categories for UI display."""
        categories_db = self.session.query(GoToListCategoryDB).order_by(GoToListCategoryDB.name).all()
        return [{'id': c.id, 'name': c.name, 'is_deletable': c.is_deletable} for c in categories_db]

    def get_talents_in_category(self, category_id: int) -> List[Talent]:
        """Gets all talents within a specific Go-To List category."""
        talents_db = self.session.query(TalentDB)\
            .join(GoToListAssignmentDB)\
            .filter(GoToListAssignmentDB.category_id == category_id)\
            .order_by(TalentDB.alias)\
            .all()
        return [t.to_dataclass(Talent) for t in talents_db]
    
    def get_talent_categories(self, talent_id: int) -> List[Dict]:
        """Returns a list of all Go-To List categories a specific talent belongs to."""
        assignments = self.session.query(GoToListCategoryDB).\
            join(GoToListAssignmentDB).\
            filter(GoToListAssignmentDB.talent_id == talent_id).\
            order_by(GoToListCategoryDB.name).all()
            
        return [{'id': c.id, 'name': c.name, 'is_deletable': c.is_deletable} for c in assignments]
    
    # --- Scene & Bloc Query Methods ---

    def get_blocs_for_schedule_view(self, year: int) -> List[ShootingBloc]:
        """Fetches shooting blocs and their scenes for the schedule tab for a given year."""
        blocs_db = self.session.query(ShootingBlocDB).filter(
            ShootingBlocDB.scheduled_year == year
        ).options(
            selectinload(ShootingBlocDB.scenes)
        ).order_by(ShootingBlocDB.scheduled_week).all()
        
        return [b.to_dataclass(ShootingBloc) for b in blocs_db]

    def get_bloc_by_id(self, bloc_id: int) -> Optional[ShootingBloc]:
        """Fetches a single shooting bloc by its ID, without its scenes."""
        bloc_db = self.session.query(ShootingBlocDB).get(bloc_id)
        return bloc_db.to_dataclass(ShootingBloc) if bloc_db else None

    def get_shot_scenes(self) -> List[Scene]:
        """Fetches all scenes that have been shot or released for the scenes tab."""
        scenes_db = self.session.query(SceneDB).populate_existing().options(
            selectinload(SceneDB.performer_contributions_rel)
        ).filter(
            SceneDB.status.in_(['shot', 'in_editing', 'ready_to_release', 'released'])
        ).all()
        return [s.to_dataclass(Scene) for s in scenes_db]

    def get_scene_for_planner(self, scene_id: int) -> Optional[Scene]:
        """Fetches a single scene with all its relationships for the SceneDialog."""
        scene_db = self.session.query(SceneDB).options(
            selectinload(SceneDB.virtual_performers),
            selectinload(SceneDB.action_segments).selectinload(ActionSegmentDB.slot_assignments),
            selectinload(SceneDB.cast) # Also load cast for salary info
        ).get(scene_id)
        return scene_db.to_dataclass(Scene) if scene_db else None

    def get_scene_history_for_talent(self, talent_id: int) -> List[Scene]:
        scenes_db = self.session.query(SceneDB)\
            .join(SceneCastDB)\
            .filter(SceneCastDB.talent_id == talent_id)\
            .filter(SceneDB.status.in_(['shot', 'in_editing', 'ready_to_release', 'released']))\
            .order_by(SceneDB.scheduled_year.desc(), SceneDB.scheduled_week.desc())\
            .all()
        return [s.to_dataclass(Scene) for s in scenes_db]
    
    def get_incomplete_scenes_for_week(self, week: int, year: int) -> List[Scene]:
        """Finds scenes scheduled for a given week that are not fully cast or are still in design."""
        scenes_db = self.session.query(SceneDB).filter(
            SceneDB.status.in_(['casting', 'design']),
            SceneDB.scheduled_week == week,
            SceneDB.scheduled_year == year
        ).options(selectinload(SceneDB.cast)).all()
        return [s.to_dataclass(Scene) for s in scenes_db]

    def get_castable_scenes_for_ui(self) -> List[Dict]:
        """
        Fetches a simplified list of scenes in 'casting' status
        that have at least one uncast role, for UI dropdowns.
        """
        scenes_db = self.session.query(SceneDB).filter(
            SceneDB.status == 'casting'
        ).options(
            selectinload(SceneDB.cast),
            selectinload(SceneDB.virtual_performers)
        ).order_by(SceneDB.scheduled_year, SceneDB.scheduled_week, SceneDB.title).all()

        results = []

        for scene in scenes_db:
            if len(scene.cast) < len(scene.virtual_performers):
                results.append({'id': scene.id, 'title': scene.title})
                
        return results

    def get_uncast_roles_for_scene_ui(self, scene_id: int) -> List[Dict]:
        """
        Fetches a list of uncast virtual performers for a given scene,
        for use in UI dropdowns.
        """
        scene_db = self.session.query(SceneDB).options(
            selectinload(SceneDB.cast),
            selectinload(SceneDB.virtual_performers)
        ).get(scene_id)

        if not scene_db: return []
        cast_vp_ids = {c.virtual_performer_id for c in scene_db.cast}
        uncast_roles = [{'id': vp.id, 'name': vp.name} for vp in scene_db.virtual_performers if vp.id not in cast_vp_ids]
        return sorted(uncast_roles, key=lambda x: x['name'])