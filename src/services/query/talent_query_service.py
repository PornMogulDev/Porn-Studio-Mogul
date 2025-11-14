import logging
from typing import Dict, List, Tuple
from collections import defaultdict
from sqlalchemy.orm import selectinload, Session

from data.game_state import Scene, Talent
from data.data_manager import DataManager
from database.db_models import (
    TalentDB, SceneDB, ActionSegmentDB,
    ShootingBlocDB, SceneCastDB
)
from services.query.game_query_service import GameQueryService
from services.calculation.talent_demand_calculator import TalentDemandCalculator
from services.models.configs import HiringConfig
from services.calculation.talent_availability_checker import TalentAvailabilityChecker
from services.calculation.shoot_results_calculator import ShootResultsCalculator

logger = logging.getLogger(__name__)

class TalentQueryService:
    def __init__(self, session_factory, data_manager: DataManager, demand_calculator: TalentDemandCalculator, 
                 query_service: GameQueryService, config: HiringConfig, 
                 availability_checker: TalentAvailabilityChecker, shoot_results_calculator: ShootResultsCalculator):
        self.session_factory = session_factory
        self.data_manager = data_manager
        self.demand_calculator = demand_calculator
        self.query_service = query_service
        self.config = config
        self.availability_checker = availability_checker
        self.shoot_results_calculator = shoot_results_calculator

    def _get_role_tags_for_display(self, scene: Scene, vp_id: int) -> List[str]:
        """Helper to get a formatted list of tags and roles for UI display."""
        _, roles_by_tag = self.availability_checker.get_vp_role_context(scene, vp_id)
        tags_with_roles = [
            f"{tag_name} ({', '.join(sorted(list(roles)))})" 
            for tag_name, roles in sorted(roles_by_tag.items())
        ]
        return tags_with_roles
    
    def _get_adjacent_weeks(self, week: int, year: int) -> Dict[str, Tuple[int, int]]:
        """Calculates the previous and next week, handling year boundaries."""
        prev_week, prev_year = (week - 1, year) if week > 1 else (52, year - 1)
        next_week, next_year = (week + 1, year) if week < 52 else (1, year + 1)
        return {"before": (prev_week, prev_year), "next": (next_week, next_year)}
    
    def _get_weekly_bookings_for_talents(self, session: Session, talent_ids: List[int]) -> Dict[Tuple[int, int], Dict[int, List[Scene]]]:
        """Efficiently fetches all scene bookings for a list of talents, grouped by week and then by talent."""
        weekly_bookings = defaultdict(lambda: defaultdict(list))
        if not talent_ids:
            return weekly_bookings
            
        cast_entries = session.query(SceneCastDB).options(selectinload(SceneCastDB.scene)).filter(SceneCastDB.talent_id.in_(talent_ids)).all()

        for entry in cast_entries:
            if entry.scene.status == 'scheduled': # Only count scheduled scenes as firm bookings
                week_key = (entry.scene.scheduled_week, entry.scene.scheduled_year)
                # We can append the DB object directly; the checker just needs to count them.
                weekly_bookings[week_key][entry.talent_id].append(entry.scene)
        return weekly_bookings

    def get_eligible_talent_for_role(self, scene_id: int, vp_id: int) -> List[TalentDB]:
        """
        Gets a virtual performer from a scene and returns a list of talent that can be cast for the role.
        """
        session = self.session_factory()
        try:
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
            
            query = session.query(TalentDB).options(
                selectinload(TalentDB.popularity_scores),
                selectinload(TalentDB.chemistry_a),
                selectinload(TalentDB.chemistry_b)
            )
            query = query.filter(TalentDB.gender == vp.gender)
            
            if vp.ethnicity != "Any":
                # Hierarchical ethnicity check for the database query
                primary_ethnicities_map = self.data_manager.generator_data.get('primary_ethnicities', {})
                if vp.ethnicity in primary_ethnicities_map:
                    # The VP requires a primary group, so we accept talent from any of its sub-groups.
                    eligible_ethnicities = primary_ethnicities_map[vp.ethnicity]
                    query = query.filter(TalentDB.ethnicity.in_(eligible_ethnicities))
                else:
                    # The VP requires a specific sub-group (or a primary group with no subs), so do a direct match.
                    query = query.filter(TalentDB.ethnicity == vp.ethnicity)

            if cast_talent_ids := {c.talent_id for c in scene_db.cast}:
                query = query.filter(TalentDB.id.notin_(cast_talent_ids))

            potential_candidates_db = query.all()

            # --- Orchestration: Pre-fetch weekly bookings for all candidates ---
            candidate_ids = [t.id for t in potential_candidates_db]
            all_weekly_bookings = self._get_weekly_bookings_for_talents(session, candidate_ids)
            scene_week_key = (scene.scheduled_week, scene.scheduled_year)
            bookings_for_this_week = all_weekly_bookings.get(scene_week_key, {})

            eligible_talents_db = []

            for talent_db in potential_candidates_db:
                adjacent_weeks = self._get_adjacent_weeks(scene.scheduled_week, scene.scheduled_year)
                
                bookings_before = all_weekly_bookings.get(adjacent_weeks['before'], {}).get(talent_db.id, [])
                bookings_current = bookings_for_this_week.get(talent_db.id, [])
                bookings_after = all_weekly_bookings.get(adjacent_weeks['next'], {}).get(talent_db.id, [])
                
                estimated_fatigue = self.shoot_results_calculator.estimate_fatigue_gain(talent_db, scene, vp.id)
                
                result = self.availability_checker.check(
                    talent_db, scene, vp.id, bloc_db, 
                    bookings_before, bookings_current, bookings_after, 
                    estimated_fatigue
                )
                if result.is_available:
                    eligible_talents_db.append(talent_db)
                
            return sorted(eligible_talents_db, key=lambda t: t.alias)
        except Exception as e:
            logger.error(f"Error getting eligible talent for role {vp_id} in scene {scene_id}: {e}", exc_info=True)
            return []
        finally:
            session.close()

    def find_available_roles_for_talent(self, talent_id: int, studio_location: str) -> List[Dict]:
        """
        Finds all uncast roles that a talent is eligible for, calculating hiring cost and availability.
        """
        with self.session_factory() as session:
            talent_db = session.query(TalentDB).options(
                selectinload(TalentDB.popularity_scores),
                selectinload(TalentDB.chemistry_a),
                selectinload(TalentDB.chemistry_b)
            ).get(talent_id)
            if not talent_db: return []
            talent_dc = talent_db.to_dataclass(Talent) # For travel fee calculation
            talent = talent_db # For availability check

            available_roles = []
            scenes_in_casting = session.query(SceneDB)\
                .options(selectinload(SceneDB.virtual_performers), selectinload(SceneDB.cast),
                        selectinload(SceneDB.action_segments).selectinload(ActionSegmentDB.slot_assignments))\
                .filter(SceneDB.status == 'casting').all()
            
            bloc_ids = {s.bloc_id for s in scenes_in_casting if s.bloc_id}
            blocs_by_id = {}
            if bloc_ids:
                blocs_db = session.query(ShootingBlocDB).filter(ShootingBlocDB.id.in_(bloc_ids)).all()
                blocs_by_id = {b.id: b for b in blocs_db}

            # --- Orchestration: Pre-fetch all bookings for the single talent ---
            all_weekly_bookings = self._get_weekly_bookings_for_talents(session, [talent_id])
            
            for scene_db in scenes_in_casting:
                scene = scene_db.to_dataclass(Scene)
                cast_talent_ids = {c.talent_id for c in scene_db.cast}
                if talent.id in cast_talent_ids: continue
                adjacent_weeks = self._get_adjacent_weeks(scene.scheduled_week, scene.scheduled_year)
    
                bookings_before = all_weekly_bookings.get(adjacent_weeks['before'], {}).get(talent_id, [])
                bookings_current = all_weekly_bookings.get((scene.scheduled_week, scene.scheduled_year), {}).get(talent_id, [])
                bookings_after = all_weekly_bookings.get(adjacent_weeks['next'], {}).get(talent_id, [])

                all_vp_ids = {vp.id for vp in scene_db.virtual_performers}
                cast_vp_ids = {c.virtual_performer_id for c in scene_db.cast}
                uncast_vp_ids = all_vp_ids - cast_vp_ids
                
                for vp_db in scene_db.virtual_performers:
                    if vp_db.id not in uncast_vp_ids: continue
                    
                    # Check for gender and ethnicity eligibility
                    if vp_db.gender != talent.gender:
                        continue
                    
                    required_ethnicity = vp_db.ethnicity
                    if required_ethnicity != "Any" and not self.data_manager.is_ethnicity_match(talent.ethnicity, required_ethnicity):
                        continue
                    
                    bloc_db = blocs_by_id.get(scene.bloc_id)
                    estimated_fatigue = self.shoot_results_calculator.estimate_fatigue_gain(talent, scene, vp_db.id)
                    result = self.availability_checker.check(
                        talent, scene, vp_db.id, bloc_db,
                        bookings_before, bookings_current, bookings_after,
                        estimated_fatigue
                    )

                    base_cost, travel_fee, total_cost = self.demand_calculator.calculate_total_demand(
                        talent_id, scene_db.id, vp_db.id, studio_location,
                        scene=scene,
                        talent=talent_dc
                    )

                    role_info = {
                        'scene_id': scene_db.id, 'scene_title': scene_db.title,
                        'virtual_performer_id': vp_db.id, 'vp_name': vp_db.name,
                        'cost': total_cost, 'base_cost': base_cost, 'travel_fee': travel_fee,
                        'tags': self._get_role_tags_for_display(scene, vp_db.id),
                        'is_available': result.is_available, 'refusal_reason': result.reason
                    }
                    
                    available_roles.append(role_info)
            return available_roles
    
    def get_role_details_for_ui(self, scene_id: int, vp_id: int) -> Dict:
        """Fetches a comprehensive dictionary of a specific role's details for UI display."""
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
            logger.error(f"Error getting role details for {vp_id} in scene {scene_id}: {e}", exc_info=True)
            return {}
        finally:
            session.close()