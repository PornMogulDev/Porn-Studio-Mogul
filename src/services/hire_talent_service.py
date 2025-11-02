import logging
import numpy as np
from dataclasses import dataclass
from typing import Dict, Optional, List, Set, Union, Tuple
from collections import defaultdict
from sqlalchemy.orm import joinedload, selectinload

from data.game_state import Talent, Scene, ActionSegment
from data.data_manager import DataManager
from database.db_models import (
    TalentDB, SceneDB, ActionSegmentDB,
    ShootingBlocDB
)
from services.query.game_query_service import GameQueryService
from services.models.configs import HiringConfig
from services.utils.role_performance_service import RolePerformanceService
from services.utils.talent_availability_checker import TalentAvailabilityChecker

logger = logging.getLogger(__name__)

class HireTalentService:
    def __init__(self, session_factory, data_manager: DataManager, query_service: GameQueryService, config: HiringConfig, availability_checker: TalentAvailabilityChecker):
        self.session_factory = session_factory
        self.data_manager = data_manager
        self.query_service = query_service
        self.config = config
        self.availability_checker = availability_checker

    def _get_role_tags_for_display(self, scene: Scene, vp_id: int) -> List[str]:
        """
        Helper to get a formatted list of tags and roles for UI display.

        Returns:
            A tuple containing:
            - A set of all action tag names the VP participates in.
            - A dictionary mapping tag names to the set of roles the VP performs in that tag.
        """
        action_tags = set()
        roles_by_tag = defaultdict(set)
        
        _, roles_by_tag = self.availability_checker._get_vp_role_context(scene, vp_id)
        tags_with_roles = [
            f"{tag_name} ({', '.join(sorted(list(roles)))})" 
            for tag_name, roles in sorted(roles_by_tag.items())
        ]
        return tags_with_roles


    def get_eligible_talent_for_role(self, scene_id: int, vp_id: int) -> List[TalentDB]:
        """
        Gets a virtual performer from a scene and returns a list of talent that can be cast for the role.
        """
        session = self.session_factory()
        try:
            # --- Step A: Gather Context ---
            scene_db = session.query(SceneDB).options(
                selectinload(SceneDB.virtual_performers),
                selectinload(SceneDB.cast),
                selectinload(SceneDB.action_segments).selectinload(ActionSegmentDB.slot_assignments)
            ).get(scene_id)
            if not scene_db: return []
            scene = scene_db.to_dataclass(Scene)

            vp = next((v for v in scene.virtual_performers if v.id == vp_id), None)
            if not vp: return []

            bloc_db = session.query(ShootingBlocDB).get(scene_db.bloc_id) if scene_db.bloc_id else None
            
            # --- Step B: Initial Database Query ---
            query = session.query(TalentDB).options(
                selectinload(TalentDB.popularity_scores),
                selectinload(TalentDB.chemistry_a),
                selectinload(TalentDB.chemistry_b)
            )
            query = query.filter(TalentDB.gender == vp.gender)
            if vp.ethnicity != "Any":
                query = query.filter(TalentDB.ethnicity == vp.ethnicity)
            if cast_talent_ids := {c.talent_id for c in scene_db.cast}:
                query = query.filter(TalentDB.id.notin_(cast_talent_ids))

            # --- Step C: In-Memory Python Filtering (Optimized) ---
            potential_candidates_db = query.all()
            eligible_talents_db = []

            for talent_db in potential_candidates_db:
                # Pass the lightweight DB object directly to the checker
                result = self.availability_checker.check(talent_db, scene, vp.id, bloc_db)
                if result.is_available:
                    eligible_talents_db.append(talent_db)
                
            return sorted(eligible_talents_db, key=lambda t: t.alias)
        except Exception as e:
            logger.error(f"Error trying to get eligible talent to cast in {vp_id} role for {scene_id} scene: {e}", exc_info=True)
            return False
        finally:
            session.close()
    
    def filter_talents_by_availability(self, talents: List[Union[Talent, TalentDB]], scene_id: int, vp_id: int) -> List[Union[Talent, TalentDB]]:
        """
        I don't think this is being used for anything at the moment.
        """
        session = self.session_factory()
        try:
            # --- Step A: Gather Context (once for all talents) ---
            scene_db = session.query(SceneDB).options(
                selectinload(SceneDB.virtual_performers),
                selectinload(SceneDB.cast),
                selectinload(SceneDB.action_segments).selectinload(ActionSegmentDB.slot_assignments)
            ).get(scene_id)
            if not scene_db: return []
            scene = scene_db.to_dataclass(Scene)

            bloc_db = session.query(ShootingBlocDB).get(scene_db.bloc_id) if scene_db.bloc_id else None

            # --- Step B: In-Memory Python Filtering (Optimized) ---
            available_talents = []
            for talent_obj in talents: # Now works with Talent or TalentDB
                result = self.availability_checker.check(talent_obj, scene, vp_id, bloc_db)
                if result.is_available:
                    available_talents.append(talent_obj)

            return available_talents
        except Exception as e:
            logger.error(f"Error trying to filter talents: {e}", exc_info=True)
            return False
        finally:
            session.close()
    
    def find_available_roles_for_talent(self, talent_id: int) -> List[Dict]:
        """
        Finds all uncast roles in 'casting' scenes that a given talent is eligible for,
        and calculates the hiring cost for each. Includes availability and refusal reasons.
        """
        session = self.session_factory()
        try:
            talent = self.query_service.get_talent_by_id(talent_id)
            if not talent: return []

            available_roles = []
            scenes_in_casting = session.query(SceneDB)\
                .options(selectinload(SceneDB.virtual_performers), selectinload(SceneDB.cast),
                        selectinload(SceneDB.action_segments).selectinload(ActionSegmentDB.slot_assignments))\
                .filter(SceneDB.status == 'casting').all()
            
            # Pre-fetch all shooting blocs for these scenes to avoid N+1 queries
            bloc_ids = {s.bloc_id for s in scenes_in_casting if s.bloc_id}
            blocs_by_id = {}
            if bloc_ids:
                blocs_db = session.query(ShootingBlocDB).filter(ShootingBlocDB.id.in_(bloc_ids)).all()
                blocs_by_id = {b.id: b for b in blocs_db}
            
            for scene_db in scenes_in_casting:
                scene = scene_db.to_dataclass(Scene); cast_talent_ids = {c.talent_id for c in scene_db.cast}
                if talent.id in cast_talent_ids: continue

                all_vp_ids = {vp.id for vp in scene_db.virtual_performers}; cast_vp_ids = {c.virtual_performer_id for c in scene_db.cast}
                uncast_vp_ids = all_vp_ids - cast_vp_ids
                
                for vp_db in scene_db.virtual_performers:
                    if vp_db.id not in uncast_vp_ids: continue
                    if not (vp_db.gender == talent.gender and (vp_db.ethnicity == "Any" or vp_db.ethnicity == talent.ethnicity)): continue
                    
                    bloc_db = blocs_by_id.get(scene.bloc_id) if scene.bloc_id else None
                    result = self.availability_checker.check(talent, scene, vp_db.id, bloc_db)

                    role_info = {
                        'scene_id': scene_db.id, 'scene_title': scene_db.title, 'virtual_performer_id': vp_db.id,
                        'vp_name': vp_db.name, 'cost': self.calculate_talent_demand(talent.id, scene_db.id, vp_db.id, scene=scene),
                        'tags': self._get_role_tags_for_display(scene, vp_db.id),
                        'is_available': result.is_available, 'refusal_reason': result.reason
                    }
                    
                    available_roles.append(role_info)
            return available_roles
        except Exception as e:
            logger.error(f"Error trying to find roles for {talent_id}: {e}", exc_info=True)
            return False
        finally:
            session.close()
    
    def calculate_talent_demand(self, talent_id: int, scene_id: int, vp_id: int, scene: Optional[Scene] = None) -> int:
        session = self.session_factory()
        try:
            talent = self.query_service.get_talent_by_id(talent_id)
            if not talent: return 0

            # If a Scene object is not passed in, fetch it from the database.
            if not scene:
                scene_db = session.query(SceneDB).options(
                    joinedload(SceneDB.virtual_performers),
                    joinedload(SceneDB.action_segments).joinedload(ActionSegmentDB.slot_assignments)
                ).get(scene_id)
                if not scene_db: return 0
                scene = scene_db.to_dataclass(Scene)

            base_demand = self.config.base_talent_demand
            performance_multiplier = 1 + (talent.performance / self.config.demand_perf_divisor)
            median_ambition = self.config.median_ambition
            ambition_demand_divisor = self.config.ambition_demand_divisor
            ambition_multiplier = 1.0 + ((talent.ambition - median_ambition) / ambition_demand_divisor)
            
            overall_popularity = sum(talent.popularity.values())

            popularity_demand_scalar = self.config.popularity_demand_scalar
            popularity_multiplier = 1.0 + (overall_popularity * popularity_demand_scalar)
            
            role_multiplier = 1.0; max_demand_mod = 1.0
            action_segments_for_calc = scene.get_expanded_action_segments(self.data_manager.tag_definitions)
            for segment in action_segments_for_calc:
                slots = scene._get_slots_for_segment(segment, self.data_manager.tag_definitions)
                for assignment in segment.slot_assignments:
                    if assignment.virtual_performer_id == vp_id:
                        try: _ , role, _ = assignment.slot_id.rsplit('_', 2)
                        except ValueError: continue
                        slot_def = next((s for s in slots if s['role'] == role), None)
                        if not slot_def: continue
                        final_mod = RolePerformanceService.get_final_modifier('demand_modifier', slot_def, segment, role)
                        max_demand_mod = max(max_demand_mod, final_mod)
            role_multiplier = max_demand_mod
            
            _, roles_by_tag = self.availability_checker._get_vp_role_context(scene, vp_id)
            preference_scores = []
            if roles_by_tag:
                for tag_name, roles in roles_by_tag.items():
                    for role in roles:
                        score = talent.tag_preferences.get(tag_name, {}).get(role, 1.0)
                        preference_scores.append(score)
            
            preference_multiplier = np.mean(preference_scores) if preference_scores else 1.0
            
            final_demand = base_demand * performance_multiplier * ambition_multiplier * role_multiplier * popularity_multiplier
            
            # A preference > 1 reduces cost; a preference < 1 increases it.
            if preference_multiplier > 0:
                final_demand /= preference_multiplier

            return max(self.config.minimum_talent_demand, int(final_demand))
        except Exception as e:
            logger.error(f"Error trying to calculate {talent_id}'s demand for {vp_id} role in {scene_id} scene: {e}", exc_info=True)
            return False
        finally:
            session.close()
    
    def get_role_details_for_ui(self, scene_id: int, vp_id: int) -> Dict:
        """
        Fetches a comprehensive dictionary of a specific role's details for UI display.
        """
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
            logger.error(f"Error trying get the details of {vp_id} role in {scene_id} scene: {e}", exc_info=True)
            return False
        finally:
            session.close()