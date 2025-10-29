import logging
import random
from typing import Dict, List, Optional, DefaultDict
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.orm.attributes import flag_modified

from data.game_state import Scene, ShootingBloc
from data.data_manager import DataManager
from services.scene_calculation_service import SceneCalculationService
from services.role_performance_service import RolePerformanceService 
from services.scene_event_service import SceneEventService
from services.talent_service import TalentService
from services.market_service import MarketService
from database.db_models import ( SceneDB, VirtualPerformerDB, ActionSegmentDB, SlotAssignmentDB,
                                MarketGroupStateDB, TalentDB, GameInfoDB, SceneCastDB, ShootingBlocDB )

logger = logging.getLogger(__name__)

class SceneService:
    def __init__(self, db_session, signals, data_manager: DataManager, 
                 talent_service: TalentService, market_service: MarketService, role_perf_service: RolePerformanceService,
                    event_service: SceneEventService):
        self.session = db_session
        self.signals = signals
        self.data_manager = data_manager
        self.talent_service = talent_service
        self.market_service = market_service
        self.event_service = event_service
        self.calculation_service = SceneCalculationService(db_session, data_manager, talent_service, market_service, role_perf_service)

    # --- UI Query Methods ---
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

        if not scene_db:
            return []

        cast_vp_ids = {c.virtual_performer_id for c in scene_db.cast}
        
        uncast_roles = []
        for vp in scene_db.virtual_performers:
            if vp.id not in cast_vp_ids:
                uncast_roles.append({'id': vp.id, 'name': vp.name})
        
        return sorted(uncast_roles, key=lambda x: x['name'])


    # --- CRUD and Logic Methods ---
    def cast_talent_for_role(self, talent_id: int, scene_id: int, virtual_performer_id: int, cost: int) -> Optional[Dict]:
        scene_db = self.session.query(SceneDB).get(scene_id)
        talent = self.talent_service.get_talent_by_id(talent_id)
        if not scene_db or not talent: return None

        new_cast_entry = SceneCastDB(
            scene_id=scene_id,
            talent_id=talent_id,
            virtual_performer_id=virtual_performer_id,
            salary=cost
        )
        scene_db.cast.append(new_cast_entry)
        
        messages = {"main_message": f"Cast {talent.alias} in '{scene_db.title}' for ${cost:,}.", "locked_message": None, "complete_message": None}

        if not scene_db.is_locked:
            scene_db.is_locked = True
            messages["locked_message"] = f"Scene '{scene_db.title}' is now locked for design changes."

        if len(scene_db.cast) == len(scene_db.virtual_performers):
            scene_db.status = 'scheduled'
            messages["complete_message"] = f"Casting complete! '{scene_db.title}' is now scheduled."
        
        return messages

    def _create_scene_for_bloc(self, bloc_db: ShootingBlocDB) -> SceneDB:
        focus_target = self.data_manager.market_data.get('viewer_groups', [{}])[0].get('name', 'N/A')
        
        new_scene_db = SceneDB(
            title="Untitled Scene", status="design", focus_target=focus_target,
            scheduled_week=bloc_db.scheduled_week, 
            scheduled_year=bloc_db.scheduled_year, bloc_id=bloc_db.id
        )
        
        default_vp_db = VirtualPerformerDB(name="Performer 1", gender="Female", ethnicity="Any")
        new_scene_db.virtual_performers.append(default_vp_db)
        
        self.session.add(new_scene_db)
        self.session.flush() 
        
        new_scene_db.title = f"Untitled Scene {new_scene_db.id}"
        return new_scene_db
    
    def create_shooting_bloc(self, week: int, year: int, num_scenes: int, settings: Dict[str, str], cost: int, name: str, policies: List[str]) -> Optional[int]:
        """Creates a new ShootingBloc and its associated blank scenes in the database."""
        try:
            bloc_db = ShootingBlocDB(
                name=name,
                scheduled_week=week,
                scheduled_year=year,
                production_settings=settings,
                production_cost=cost, # This now receives the correct integer cost
                on_set_policies=policies
            )
            self.session.add(bloc_db)
            self.session.flush() # Get the ID for the bloc

            for _ in range(num_scenes):
                scene_db = self._create_scene_for_bloc(bloc_db)
            
            return bloc_db.id
        except Exception as e:
            # Proper logging should be added here in a real application
            logger.error(f"[ERROR] Failed to create shooting bloc in DB: {e}")
            self.session.rollback()
            return None

    def create_blank_scene(self, week: int, year: int) -> int:
        focus_target = self.data_manager.market_data.get('viewer_groups', [{}])[0].get('name', 'N/A')
        
        new_scene_db = SceneDB(title="Untitled Scene", status="design", focus_target=focus_target,
                               scheduled_week=week, scheduled_year=year)
        
        default_vp_db = VirtualPerformerDB(name="Performer 1", gender="Female", ethnicity="Any")
        new_scene_db.virtual_performers.append(default_vp_db)
        
        self.session.add(new_scene_db)
        self.session.flush() 
        
        new_scene_db.title = f"Untitled Scene {new_scene_db.id}"
        
        self.signals.scenes_changed.emit()
        return new_scene_db.id

    def delete_scene(self, scene_id: int, penalty_percentage: float = 0.0) -> Optional[str]:
        scene_db = self.session.query(SceneDB).options(selectinload(SceneDB.cast)).get(scene_id)
        if scene_db:
            scene_title = scene_db.title
            
            if penalty_percentage > 0 and scene_db.cast:
                total_salary = sum(c.salary for c in scene_db.cast)
                cost = int(total_salary * penalty_percentage)
                if cost > 0:
                    money_info = self.session.query(GameInfoDB).filter_by(key='money').one()
                    current_money = int(money_info.value)
                    new_money = current_money - cost
                    money_info.value = str(new_money)
                    self.signals.notification_posted.emit(f"Paid ${cost:,} in severance for cancelling '{scene_title}'.")
                    self.signals.money_changed.emit(new_money)
            
            self.session.delete(scene_db)
            # scenes_changed signal is emitted from controller
            return scene_title
        return None

    def update_scene_full(self, scene_data: Scene):
        """
        Updates an entire scene record from a Scene dataclass.
        This is a more robust way for the UI to commit all its changes at once.
        """
        scene_db = self.session.query(SceneDB).options(
            selectinload(SceneDB.virtual_performers),
            selectinload(SceneDB.action_segments).selectinload(ActionSegmentDB.slot_assignments)
        ).get(scene_data.id)
        if not scene_db:
            return {}
        if len(scene_db.cast) > 0:
            logger.warning(f"Attempted to edit scene {scene_data.id} which is already cast. Aborting save.")
            return {}

        vp_id_map = {}

        existing_vps = {vp.id: vp for vp in scene_db.virtual_performers}
        updated_vps = []
        new_vp_temp_objects = {}

        for vp_data in scene_data.virtual_performers:
            if vp_data.id is not None and vp_data.id > 0 and vp_data.id in existing_vps:
                vp_db = existing_vps.pop(vp_data.id)
                vp_db.name, vp_db.gender, vp_db.ethnicity, vp_db.disposition = vp_data.name, vp_data.gender, vp_data.ethnicity, vp_data.disposition
                updated_vps.append(vp_db)
            else: 
                temp_id = vp_data.id 
                new_vp_db = VirtualPerformerDB.from_dataclass(vp_data)
                new_vp_db.id = None 
                updated_vps.append(new_vp_db)
                if temp_id is not None:
                    new_vp_temp_objects[temp_id] = new_vp_db
        
        scene_db.virtual_performers = updated_vps
        self.session.flush()

        for temp_id, vp_db_object in new_vp_temp_objects.items():
            if vp_db_object.id:
                vp_id_map[temp_id] = vp_db_object.id

        # Update simple attributes, excluding those needing ID remapping
        for key in ['title', 'status', 'focus_target', 'total_runtime_minutes', 'scheduled_week', 'scheduled_year', 'global_tags', 'is_locked', 'dom_sub_dynamic_level']:
             if hasattr(scene_data, key):
                 setattr(scene_db, key, getattr(scene_data, key))

        # Manually remap protagonist IDs
        scene_db.protagonist_vp_ids = [vp_id_map.get(pid, pid) for pid in scene_data.protagonist_vp_ids]

        # Remap assigned_tags with the new permanent IDs
        corrected_assigned_tags = {}
        for tag_name, vp_ids in scene_data.assigned_tags.items():
            corrected_ids = [vp_id_map.get(vp_id, vp_id) for vp_id in vp_ids]
            corrected_assigned_tags[tag_name] = corrected_ids
        scene_db.assigned_tags = corrected_assigned_tags

        # Update Action Segments
        existing_segments = {seg.id: seg for seg in scene_db.action_segments}
        updated_segments = []
        for seg_data in scene_data.action_segments:
            seg_db = None
            if seg_data.id is not None and seg_data.id > 0 and seg_data.id in existing_segments:
                seg_db = existing_segments.pop(seg_data.id)
                seg_db.tag_name, seg_db.runtime_percentage, seg_db.parameters = seg_data.tag_name, seg_data.runtime_percentage, seg_data.parameters
            else: # New Segment
                seg_db = ActionSegmentDB.from_dataclass(seg_data)
                seg_db.id = None
                seg_db.slot_assignments = []
            
            existing_assignments = {sa.slot_id: sa for sa in seg_db.slot_assignments}
            updated_assignments = []
            for assign_data in seg_data.slot_assignments:
                final_vp_id = vp_id_map.get(assign_data.virtual_performer_id, assign_data.virtual_performer_id)

                assign_db = None
                if assign_data.slot_id in existing_assignments:
                    assign_db = existing_assignments.pop(assign_data.slot_id)
                    assign_db.virtual_performer_id = final_vp_id
                else: # New Assignment
                    assign_db = SlotAssignmentDB.from_dataclass(assign_data)
                    assign_db.virtual_performer_id = final_vp_id
                
                updated_assignments.append(assign_db)
            
            seg_db.slot_assignments = updated_assignments
            updated_segments.append(seg_db)
            
        scene_db.action_segments = updated_segments

        self.signals.scenes_changed.emit()
        return vp_id_map

    def start_editing_scene(self, scene_id: int, editing_tier_id: str) -> tuple[bool, int]:
        """Begins the editing process for a shot scene."""
        scene_db = self.session.query(SceneDB).get(scene_id)
        if not scene_db or scene_db.status != 'shot':
            return False, 0

        editing_options = self.data_manager.post_production_data.get('editing_tiers', [])
        tier_data = next((t for t in editing_options if t['id'] == editing_tier_id), None)
        if not tier_data:
            return False, 0

        cost = tier_data.get('cost', 0)
        money_info = self.session.query(GameInfoDB).filter_by(key='money').one()
        current_money = int(money_info.value)
        if current_money < cost:
            self.signals.notification_posted.emit("Not enough money for this editing option.")
            return False, 0

        # Deduct cost and update scene
        money_info.value = str(current_money - cost)
        scene_db.status = 'in_editing'
        scene_db.weeks_remaining = tier_data.get('weeks', 2)
        
        # Store the choice
        new_choices = scene_db.post_production_choices.copy() if scene_db.post_production_choices else {}
        new_choices['editing_tier'] = editing_tier_id
        scene_db.post_production_choices = new_choices
        flag_modified(scene_db, "post_production_choices") # Important for JSON mutation

        return True, cost

    def release_scene(self, scene_id: int) -> Dict:
        scene_db = self.session.query(SceneDB).get(scene_id)
        if not (scene_db and scene_db.status == 'ready_to_release'):
            return {}

        scene = scene_db.to_dataclass(Scene)
        revenue = self.calculation_service.calculate_revenue(scene) 
        self.talent_service.update_popularity_from_scene(scene_id) 

        # Market Discovery Logic
        discovery_threshold = self.data_manager.game_config.get("market_discovery_interest_threshold", 1.5)
        num_to_discover = self.data_manager.game_config.get("market_discoveries_per_scene", 2)

        all_new_discoveries = DefaultDict(list)
        market_did_change = False

        for group_name, interest in scene.viewer_group_interest.items():
            if interest >= discovery_threshold:
                market_state_db = self.session.query(MarketGroupStateDB).get(group_name)
                if not market_state_db: continue
                
                # Find which sentiments contributed most to this scene for this group
                potential_discoveries = self.market_service.get_potential_discoveries(scene, group_name)
                
                current_discovered = market_state_db.discovered_sentiments
                
                newly_discovered_count = 0
                market_did_change = True
                # Shuffle to add randomness, then sort by impact
                random.shuffle(potential_discoveries)
                potential_discoveries.sort(key=lambda x: x['impact'], reverse=True)

                for item in potential_discoveries:
                    if newly_discovered_count >= num_to_discover: break
                    
                    sentiment_type = item['type']
                    tag_name = item['tag']
                    
                    # Check if we already know this one
                    if tag_name not in current_discovered.get(sentiment_type, []):
                        if sentiment_type not in current_discovered:
                            current_discovered[sentiment_type] = []
                        current_discovered[sentiment_type].append(tag_name)
                        all_new_discoveries[group_name].append(tag_name)
                        newly_discovered_count += 1
                
                if newly_discovered_count > 0:
                    market_state_db.discovered_sentiments = current_discovered
                    flag_modified(market_state_db, "discovered_sentiments")
        
        scene_db.revenue = revenue
        scene_db.status = 'released'
        scene_db.viewer_group_interest = scene.viewer_group_interest
        scene_db.revenue_modifier_details = scene.revenue_modifier_details

        money_info = self.session.query(GameInfoDB).filter_by(key='money').one()
        new_money = int(float(money_info.value)) + revenue
        money_info.value = str(new_money)

        return {
            'discoveries': dict(all_new_discoveries), 'revenue': revenue,
            'title': scene.title, 'new_money': new_money,
            'market_changed': market_did_change
        }

    def shoot_scene(self, scene_db: SceneDB) -> bool:
        """
        Begins shooting a scene. This is the entry point from TimeService.
        It checks for an interactive event. If one occurs, it signals the UI and
        returns True to pause the time advancement. Otherwise, it completes
        the shoot and returns False.
        """
        # Ensure the dataclass is fully hydrated for the event check
        scene = self.session.query(SceneDB).options(
            selectinload(SceneDB.virtual_performers),
            selectinload(SceneDB.action_segments).selectinload(ActionSegmentDB.slot_assignments),
            selectinload(SceneDB.cast)
        ).get(scene_db.id).to_dataclass(Scene)
        
        event_payload = self.event_service.check_for_shoot_event(scene)

        if event_payload:
            # An event occurred. Emit signal and stop. Controller will resume.
            self.signals.interactive_event_triggered.emit(
                event_payload['event_data'],
                event_payload['scene_id'],
                event_payload['talent_id']
            )
            return True # Indicates that an event has paused the process
        else:
            # No event. Proceed with the full shooting process.
            self._continue_shoot_scene(scene.id, {})
            return False # Indicates the process completed normally

    def _continue_shoot_scene(self, scene_id: int, shoot_modifiers: Dict):
        """
        The second part of the shooting process, either called directly if
        no event occurs, or by the controller after an event is resolved.
        """
        scene_db = self.session.query(SceneDB).options(
            selectinload(SceneDB.cast)
        ).get(scene_id)
        
        if not scene_db:
            logger.error(f"[ERROR] _continue_shoot_scene: Scene ID {scene_id} not found.")
            return

        self.calculation_service.calculate_shoot_results(scene_db, shoot_modifiers)