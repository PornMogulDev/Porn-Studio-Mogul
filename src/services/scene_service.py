import logging
import random
from typing import Dict, List, Optional, DefaultDict
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.orm.attributes import flag_modified

from data.game_state import Scene, ShootingBloc, Talent
from data.data_manager import DataManager
from database.db_models import ( SceneDB, VirtualPerformerDB, ActionSegmentDB, SlotAssignmentDB,
                                MarketGroupStateDB, TalentDB, GameInfoDB, SceneCastDB, ShootingBlocDB )
from services.service_config import SceneCalculationConfig
from services.email_service import EmailService
from services.role_performance_service import RolePerformanceService
from services.scene_calculation_service import SceneCalculationService
from services.scene_event_service import SceneEventService
from services.talent_service import TalentService
from services.market_service import MarketService
from services.revenue_calculator import RevenueCalculator

logger = logging.getLogger(__name__)

class SceneService:
    def __init__(self, db_session, signals, data_manager: DataManager, 
                 talent_service: TalentService, market_service: MarketService, 
                 email_service: EmailService, calculation_service: 'SceneCalculationService',
                 revenue_calculator: RevenueCalculator):
        self.session = db_session
        self.signals = signals
        self.data_manager = data_manager
        self.talent_service = talent_service
        self.market_service = market_service
        self.email_service = email_service
        self.calculation_service = calculation_service
        self.revenue_calculator = revenue_calculator

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
    def _cast_talent_for_role_internal(self, talent_id: int, scene_id: int, virtual_performer_id: int, cost: int) -> Optional[Dict]:
        """
        Internal logic for casting. Does NOT commit the transaction.
        This allows it to be reused by methods that need to perform multiple
        castings in a single transaction.
        """
        scene_db = self.session.query(SceneDB).get(scene_id)
        talent = self.talent_service.get_talent_by_id(talent_id)
        if not scene_db or not talent: return None

        new_cast_entry = SceneCastDB(
            scene_id=scene_id, talent_id=talent_id,
            virtual_performer_id=virtual_performer_id, salary=cost
        )
        scene_db.cast.append(new_cast_entry)

        messages = {
            "main_message": f"Cast {talent.alias} in '{scene_db.title}' for ${cost:,}.",
            "locked_message": None, "complete_message": None
        }

        if not scene_db.is_locked:
            scene_db.is_locked = True
            messages["locked_message"] = f"Scene '{scene_db.title}' is now locked for design changes."

        if len(scene_db.cast) == len(scene_db.virtual_performers):
            scene_db.status = 'scheduled'
            messages["complete_message"] = f"Casting complete! '{scene_db.title}' is now scheduled."
        
        return messages
    
    def cast_talent_for_role(self, talent_id: int, scene_id: int, virtual_performer_id: int, cost: int) -> bool:
        """Public method for casting a single talent, handling the full transaction."""
        try:
            result = self._cast_talent_for_role_internal(talent_id, scene_id, virtual_performer_id, cost)
            if result:
                self.session.commit()
                self.signals.notification_posted.emit(result['main_message'])
                if result['locked_message']: self.signals.notification_posted.emit(result['locked_message'])
                if result['complete_message']: self.signals.notification_posted.emit(result['complete_message'])
                self.signals.scenes_changed.emit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error casting talent {talent_id} for role {virtual_performer_id} in scene {scene_id}: {e}", exc_info=True)
            self.session.rollback()
            return False

    def cast_talent_for_multiple_roles(self, talent_id: int, roles: List[Dict]) -> bool:
        """Casts a single talent for multiple roles within a single transaction."""
        try:
            for role in roles:
                self._cast_talent_for_role_internal(talent_id, role['scene_id'], role['virtual_performer_id'], role['cost'])
            self.session.commit()
            self.signals.notification_posted.emit(f"Successfully cast talent in {len(roles)} role(s).")
            self.signals.scenes_changed.emit()
            return True
        except Exception as e:
            logger.error(f"Error in multi-cast for talent {talent_id}: {e}", exc_info=True)
            self.session.rollback()
            self.signals.notification_posted.emit(f"An error occurred during multi-casting. Operation cancelled.")
            return False

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
    
    def create_shooting_bloc(self, week: int, year: int, num_scenes: int, settings: Dict[str, str], cost: int, name: str, policies: List[str]) -> bool:
        """Creates a new ShootingBloc and its associated blank scenes in the database."""
        try:
            # 1. Deduct money from game state
            money_info = self.session.query(GameInfoDB).filter_by(key='money').one()
            current_money = int(float(money_info.value))
            new_money = current_money - cost
            money_info.value = str(new_money)

            # 2. Create the bloc and scenes
            bloc_db = ShootingBlocDB(
                name=name, scheduled_week=week, scheduled_year=year,
                production_settings=settings, production_cost=cost, on_set_policies=policies
            )
            self.session.add(bloc_db)
            self.session.flush() # Get the ID for the bloc

            for _ in range(num_scenes):
                self._create_scene_for_bloc(bloc_db)
            
            # 3. Commit and signal success
            self.session.commit()
            self.signals.notification_posted.emit(f"Shooting bloc '{name}' planned. Cost: ${cost:,}")
            self.signals.money_changed.emit(new_money)
            self.signals.scenes_changed.emit()
            return True
        except Exception as e:
            logger.error(f"[ERROR] Failed to create shooting bloc in DB: {e}")
            self.session.rollback()
            self.signals.notification_posted.emit("Error: Failed to plan shooting bloc.")
            return False

    def create_blank_scene(self, week: int, year: int) -> int:
        try:
            focus_target = self.data_manager.market_data.get('viewer_groups', [{}])[0].get('name', 'N/A')
            
            new_scene_db = SceneDB(title="Untitled Scene", status="design", focus_target=focus_target,
                                   scheduled_week=week, scheduled_year=year)
            
            default_vp_db = VirtualPerformerDB(name="Performer 1", gender="Female", ethnicity="Any")
            new_scene_db.virtual_performers.append(default_vp_db)
            
            self.session.add(new_scene_db)
            self.session.flush() 
            
            new_scene_db.title = f"Untitled Scene {new_scene_db.id}"
            
            self.session.commit()
            self.signals.scenes_changed.emit()
            return new_scene_db.id
        except Exception as e:
            logger.error(f"Error creating blank scene: {e}", exc_info=True)
            self.session.rollback()
            return -1

    def delete_scene(self, scene_id: int, penalty_percentage: float = 0.0, silent: bool = False, commit: bool = True) -> bool:
        try:
            scene_db = self.session.query(SceneDB).options(selectinload(SceneDB.cast)).get(scene_id)
            if not scene_db:
                return False

            scene_title = scene_db.title
            
            if penalty_percentage > 0 and scene_db.cast:
                total_salary = sum(c.salary for c in scene_db.cast)
                cost = int(total_salary * penalty_percentage)
                if cost > 0:
                    money_info = self.session.query(GameInfoDB).filter_by(key='money').one()
                    current_money = int(float(money_info.value))
                    new_money = current_money - cost
                    money_info.value = str(new_money)
                    self.signals.notification_posted.emit(f"Paid ${cost:,} in severance for cancelling '{scene_title}'.")
                    self.signals.money_changed.emit(new_money)
            
            self.session.delete(scene_db)
            if commit:
                self.session.commit()
            if not silent:
                self.signals.notification_posted.emit(f"Scene '{scene_title}' has been deleted.")
            self.signals.scenes_changed.emit()
            return True
        except Exception as e:
            logger.error(f"Error deleting scene {scene_id}: {e}", exc_info=True)
            self.session.rollback()
            return False

    def update_scene_full(self, scene_data: Scene) -> Dict:
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
        try:
            vp_id_map = {}
            existing_vps = {vp.id: vp for vp in scene_db.virtual_performers}
            updated_vps = []
            new_vp_temp_objects = {}

            for vp_data in scene_data.virtual_performers:
                if vp_data.id > 0 and vp_data.id in existing_vps:
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

            for key in ['title', 'status', 'focus_target', 'total_runtime_minutes', 'scheduled_week', 'scheduled_year', 'global_tags', 'is_locked', 'dom_sub_dynamic_level']:
                 if hasattr(scene_data, key):
                     setattr(scene_db, key, getattr(scene_data, key))

            scene_db.protagonist_vp_ids = [vp_id_map.get(pid, pid) for pid in scene_data.protagonist_vp_ids]

            corrected_assigned_tags = {}
            for tag_name, vp_ids in scene_data.assigned_tags.items():
                corrected_ids = [vp_id_map.get(vp_id, vp_id) for vp_id in vp_ids]
                corrected_assigned_tags[tag_name] = corrected_ids
            scene_db.assigned_tags = corrected_assigned_tags

            existing_segments = {seg.id: seg for seg in scene_db.action_segments}
            updated_segments = []
            for seg_data in scene_data.action_segments:
                seg_db = None
                if seg_data.id > 0 and seg_data.id in existing_segments:
                    seg_db = existing_segments.pop(seg_data.id)
                    seg_db.tag_name, seg_db.runtime_percentage, seg_db.parameters = seg_data.tag_name, seg_data.runtime_percentage, seg_data.parameters
                else:
                    seg_db = ActionSegmentDB.from_dataclass(seg_data)
                    seg_db.id = None; seg_db.slot_assignments = []
                
                existing_assignments = {sa.slot_id: sa for sa in seg_db.slot_assignments}
                updated_assignments = []
                for assign_data in seg_data.slot_assignments:
                    final_vp_id = vp_id_map.get(assign_data.virtual_performer_id, assign_data.virtual_performer_id)
                    assign_db = None
                    if assign_data.slot_id in existing_assignments:
                        assign_db = existing_assignments.pop(assign_data.slot_id)
                        assign_db.virtual_performer_id = final_vp_id
                    else:
                        assign_db = SlotAssignmentDB.from_dataclass(assign_data)
                        assign_db.virtual_performer_id = final_vp_id
                    updated_assignments.append(assign_db)
                
                seg_db.slot_assignments = updated_assignments
                updated_segments.append(seg_db)
            scene_db.action_segments = updated_segments
            
            self.session.commit()
            self.signals.scenes_changed.emit()
            return vp_id_map
        except Exception as e:
            logger.error(f"Error updating scene {scene_data.id}: {e}", exc_info=True)
            self.session.rollback()
            return {}
        
    def start_editing_scene(self, scene_id: int, editing_tier_id: str) -> tuple[bool, int]:
        """Begins the editing process for a shot scene."""
        scene_db = self.session.query(SceneDB).get(scene_id)
        if not scene_db or scene_db.status != 'shot':
            return False, 0

        editing_options = self.data_manager.post_production_data.get('editing_tiers', [])
        tier_data = next((t for t in editing_options if t['id'] == editing_tier_id), None)
        if not tier_data:
            return False, 0

        try:
            cost = tier_data.get('cost', 0)
            money_info = self.session.query(GameInfoDB).filter_by(key='money').one()
            current_money = int(float(money_info.value))

            new_money = current_money - cost
            money_info.value = str(new_money)
            scene_db.status = 'in_editing'
            scene_db.weeks_remaining = tier_data.get('weeks', 2)
            
            new_choices = scene_db.post_production_choices.copy() if scene_db.post_production_choices else {}
            new_choices['editing_tier'] = editing_tier_id
            scene_db.post_production_choices = new_choices
            flag_modified(scene_db, "post_production_choices")

            self.session.commit()
            self.signals.money_changed.emit(new_money)
            self.signals.notification_posted.emit(f"Editing started for '{scene_db.title}'. Cost: ${cost:,}")
            self.signals.scenes_changed.emit()
            return True, cost
        except Exception as e:
            logger.error(f"Error starting editing for scene {scene_id}: {e}", exc_info=True)
            self.session.rollback()
            return False, 0

    def release_scene(self, scene_id: int) -> Dict:
        scene_db = self.session.query(SceneDB).get(scene_id)
        if not (scene_db and scene_db.status == 'ready_to_release'):
            return {}

        try:
            # --- 1. GATHER DATA ---
            scene = scene_db.to_dataclass(Scene)
            talent_ids = list(scene.final_cast.values())
            cast_talents_db = self.session.query(TalentDB).filter(TalentDB.id.in_(talent_ids)).all()
            cast_talents_dc = [t.to_dataclass(Talent) for t in cast_talents_db]
            
            all_market_states = self.market_service.get_all_market_states()
            all_resolved_groups = self.market_service.get_all_resolved_group_data()

            # --- 2. DELEGATE CALCULATION ---
            revenue_result = self.revenue_calculator.calculate_revenue(
                scene, cast_talents_dc, all_market_states, all_resolved_groups
            )

            # --- 3. APPLY RESULTS ---
            revenue = revenue_result.total_revenue
            self.talent_service.update_popularity_from_scene(scene_id)  
    
            # Market Discovery Logic
            discovery_threshold = self.data_manager.game_config.get("market_discovery_interest_threshold", 1.5)
            num_to_discover = self.data_manager.game_config.get("market_discoveries_per_scene", 2)
    
            all_new_discoveries = DefaultDict(list)
            market_did_change = False
    
            for group_name, interest in revenue_result.viewer_group_interest.items():
                if interest < discovery_threshold:
                    continue
                    
                market_state_db = self.session.query(MarketGroupStateDB).get(group_name)
                if not market_state_db: continue
                
                # Find which sentiments contributed most to this scene for this group
                potential_discoveries = self.market_service.get_potential_discoveries(scene, group_name)
                
                current_discovered = market_state_db.discovered_sentiments
                
                newly_discovered_count = 0

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
                        market_did_change = True
                
                if newly_discovered_count > 0:
                    market_state_db.discovered_sentiments = current_discovered
                    flag_modified(market_state_db, "discovered_sentiments")

            # Update market saturation
            for group_name, cost in revenue_result.market_saturation_updates.items():
                market_state_db = self.session.query(MarketGroupStateDB).get(group_name)
                if market_state_db:
                    market_state_db.current_saturation = max(0, market_state_db.current_saturation - cost)
        
            scene_db.revenue = revenue
            scene_db.status = 'released'
            scene_db.viewer_group_interest = revenue_result.viewer_group_interest
            scene_db.revenue_modifier_details = revenue_result.revenue_modifier_details
    
            money_info = self.session.query(GameInfoDB).filter_by(key='money').one()
            new_money = int(float(money_info.value)) + revenue
            money_info.value = str(new_money)

            # Pass the email service in via __init__ and call it
            if discoveries := dict(all_new_discoveries):
                self.email_service.create_market_discovery_email(scene.title, discoveries, commit=False)

            self.session.commit()

            return {
                'discoveries': discoveries, 'revenue': revenue,
                'title': scene.title, 'new_money': new_money,
                'market_changed': market_did_change
            }
        except Exception as e:
            logger.error(f"Error releasing scene {scene_id}: {e}", exc_info=True)
            self.session.rollback()
            return {}

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

    def process_weekly_post_production(self) -> List[SceneDB]:
        """
        Updates weeks_remaining for scenes in editing and finalizes them if ready.
        Returns a list of scenes that finished editing this week.
        """
        edited_scenes = []
        editing_scenes_db = self.session.query(SceneDB).filter_by(status='in_editing').all()
        for scene_db in editing_scenes_db:
            scene_db.weeks_remaining -= 1
            if scene_db.weeks_remaining <= 0:
                self.calculation_service.apply_post_production_effects(scene_db)
                edited_scenes.append(scene_db)
        return edited_scenes