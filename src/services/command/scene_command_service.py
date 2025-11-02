import logging
import random
from typing import Dict, List, Optional, DefaultDict
from sqlalchemy.orm import selectinload, Session
from sqlalchemy.orm.attributes import flag_modified

from core.game_signals import GameSignals
from data.game_state import Scene, Talent
from data.data_manager import DataManager
from database.db_models import ( SceneDB, VirtualPerformerDB, ActionSegmentDB, SlotAssignmentDB,
                                TalentDB, GameInfoDB, SceneCastDB, ShootingBlocDB,
                                 MarketGroupStateDB )
from services.query.game_query_service import GameQueryService
from services.command.talent_command_service import TalentCommandService
from services.email_service import EmailService
from services.events.scene_event_service import SceneEventService
from services.market_service import MarketService
from services.calculation.scene_orchestrator import SceneOrchestrator
from services.calculation.revenue_calculator import RevenueCalculator

logger = logging.getLogger(__name__)

class SceneCommandService:
    """
    Command service for scene-related database operations.
    
    SESSION MANAGEMENT PATTERN (Reference Implementation):
    ------------------------------------------------------
    1. Store session_factory, NOT a session instance
    2. Each public method creates its own session
    3. Use try-except-finally with commit/rollback/close
    4. Helper methods receive session as parameter
    5. Methods called by TimeService receive session parameter (TimeService manages transaction)
    
    Example Pattern:
        def public_method(self, ...):
            session = self.session_factory()
            try:
                # Do work
                session.commit()
                return result
            except Exception as e:
                session.rollback()
                logger.error(...)
                return error_value
            finally:
                session.close()
    """
    
    def __init__(self, session_factory, signals: GameSignals, data_manager: DataManager, query_service: GameQueryService, 
             talent_command_service: TalentCommandService, market_service: MarketService, 
             email_service: EmailService, calculation_service: 'SceneOrchestrator',
             revenue_calculator: RevenueCalculator):
        self.session_factory = session_factory
        self.signals = signals
        self.data_manager = data_manager
        self.query_service = query_service
        self.talent_command_service = talent_command_service
        self.market_service = market_service
        self.email_service = email_service
        self.calculation_service = calculation_service
        self.revenue_calculator = revenue_calculator
        self.event_service = None # Late-binding

    # --- CRUD and Logic Methods ---
    def _cast_talent_for_role_internal(self, session: Session, talent_id: int, scene_id: int, virtual_performer_id: int, cost: int) -> Optional[Dict]:
        """
        Internal helper for casting logic. Does NOT commit.
        Receives session as parameter to work within caller's transaction.
        """
        scene_db = session.query(SceneDB).get(scene_id)
        talent = self.query_service.get_talent_by_id(talent_id)
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
        """Public method for casting a single talent. Creates and manages its own session."""
        session = self.session_factory()
        try:
            result = self._cast_talent_for_role_internal(session, talent_id, scene_id, virtual_performer_id, cost)
            if result:
                session.commit()
                self.signals.notification_posted.emit(result['main_message'])
                if result['locked_message']: self.signals.notification_posted.emit(result['locked_message'])
                if result['complete_message']: self.signals.notification_posted.emit(result['complete_message'])
                self.signals.scenes_changed.emit()
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error casting talent {talent_id} for role {virtual_performer_id} in scene {scene_id}: {e}", exc_info=True)
            return False
        finally:
            session.close()

    def cast_talent_for_multiple_roles(self, talent_id: int, roles: List[Dict]) -> bool:
        """Casts a single talent for multiple roles within a single transaction."""
        session = self.session_factory()
        try:
            for role in roles:
                self._cast_talent_for_role_internal(session, talent_id, role['scene_id'], role['virtual_performer_id'], role['cost'])
            session.commit()
            self.signals.notification_posted.emit(f"Successfully cast talent in {len(roles)} role(s).")
            self.signals.scenes_changed.emit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error in multi-cast for talent {talent_id}: {e}", exc_info=True)
            self.signals.notification_posted.emit(f"An error occurred during multi-casting. Operation cancelled.")
            return False
        finally:
            session.close()

    def _create_scene_for_bloc(self, session: Session, bloc_db: ShootingBlocDB) -> SceneDB:
        """Helper to create a scene within a bloc. Receives session from caller."""
        focus_target = self.data_manager.market_data.get('viewer_groups', [{}])[0].get('name', 'N/A')
        
        new_scene_db = SceneDB(
            title="Untitled Scene", status="design", focus_target=focus_target,
            scheduled_week=bloc_db.scheduled_week, 
            scheduled_year=bloc_db.scheduled_year, bloc_id=bloc_db.id
        )
        
        default_vp_db = VirtualPerformerDB(name="Performer 1", gender="Female", ethnicity="Any")
        new_scene_db.virtual_performers.append(default_vp_db)
        
        session.add(new_scene_db)
        session.flush() 
        
        new_scene_db.title = f"Untitled Scene {new_scene_db.id}"
        return new_scene_db
    
    def calculate_shooting_bloc_cost(self, num_scenes: int, settings: Dict[str, str], policies: List[str]) -> int:
        """Calculates the authoritative cost for creating a shooting bloc."""
        total_cost_per_scene = 0

        # Special handling for Camera cost
        cam_equip_tier_name = settings.get("Camera Equipment")
        cam_setup_tier_name = settings.get("Camera Setup")
        
        equip_cost = 0
        if cam_equip_tier_name:
            tiers = self.data_manager.production_settings_data.get("Camera Equipment", [])
            tier_info = next((t for t in tiers if t['tier_name'] == cam_equip_tier_name), None)
            if tier_info:
                equip_cost = tier_info.get('cost_per_scene', 0)

        setup_multiplier = 1.0
        if cam_setup_tier_name:
            tiers = self.data_manager.production_settings_data.get("Camera Setup", [])
            tier_info = next((t for t in tiers if t['tier_name'] == cam_setup_tier_name), None)
            if tier_info:
                setup_multiplier = tier_info.get('cost_multiplier', 1.0)
        
        total_cost_per_scene += equip_cost * setup_multiplier

        # Add costs from all other standard categories
        for category, tier_name in settings.items():
            if category in ["Camera Equipment", "Camera Setup"]: continue
            tiers = self.data_manager.production_settings_data.get(category, [])
            tier_info = next((t for t in tiers if t['tier_name'] == tier_name), None)
            if tier_info:
                total_cost_per_scene += tier_info.get('cost_per_scene', 0)
        settings_cost = total_cost_per_scene * num_scenes

        policies_cost = sum(self.data_manager.on_set_policies_data.get(p_id, {}).get('cost_per_bloc', 0) for p_id in policies)
        
        return int(settings_cost + policies_cost)
    
    def create_shooting_bloc(self, week: int, year: int, num_scenes: int, settings: Dict[str, str], cost: int, name: str, policies: List[str]) -> bool:
        """Creates a new ShootingBloc and its associated blank scenes in the database."""
        session = self.session_factory()
        try:
            money_info = session.query(GameInfoDB).filter_by(key='money').one()
            current_money = int(float(money_info.value))
            new_money = current_money - cost
            money_info.value = str(new_money)

            bloc_db = ShootingBlocDB(
                name=name, scheduled_week=week, scheduled_year=year,
                production_settings=settings, production_cost=cost, on_set_policies=policies
            )
            session.add(bloc_db)
            session.flush()

            for _ in range(num_scenes):
                self._create_scene_for_bloc(session.bloc_db)
            
            session.commit()
            self.signals.notification_posted.emit(f"Shooting bloc '{name}' planned. Cost: ${cost:,}")
            self.signals.money_changed.emit(new_money)
            self.signals.scenes_changed.emit()
            return True
        except Exception as e:
            logger.error(f"[ERROR] Failed to create shooting bloc in DB: {e}")
            session.rollback()
            self.signals.notification_posted.emit("Error: Failed to plan shooting bloc.")
            return False
        finally:
            session.close()

    def create_blank_scene(self, week: int, year: int) -> int:
        session = self.session_factory()
        try:
            focus_target = self.data_manager.market_data.get('viewer_groups', [{}])[0].get('name', 'N/A')
            
            new_scene_db = SceneDB(title="Untitled Scene", status="design", focus_target=focus_target,
                                   scheduled_week=week, scheduled_year=year)
            
            default_vp_db = VirtualPerformerDB(name="Performer 1", gender="Female", ethnicity="Any")
            new_scene_db.virtual_performers.append(default_vp_db)
            
            session.add(new_scene_db)
            session.flush() 
            
            new_scene_db.title = f"Untitled Scene {new_scene_db.id}"
            
            session.commit()
            self.signals.scenes_changed.emit()
            return new_scene_db.id
        except Exception as e:
            logger.error(f"Error creating blank scene: {e}", exc_info=True)
            session.rollback()
            return -1
        finally:
            session.close()

    def delete_scene(self, scene_id: int, penalty_percentage: float = 0.0, silent: bool = False, commit: bool = True) -> bool:
        session = self.session_factory()
        try:
            scene_db = session.query(SceneDB).options(selectinload(SceneDB.cast)).get(scene_id)
            if not scene_db: return False
            scene_title = scene_db.title
            
            if penalty_percentage > 0 and scene_db.cast:
                total_salary = sum(c.salary for c in scene_db.cast)
                cost = int(total_salary * penalty_percentage)
                if cost > 0:
                    money_info = session.query(GameInfoDB).filter_by(key='money').one()
                    current_money = int(float(money_info.value))
                    new_money = current_money - cost
                    money_info.value = str(new_money)
                    self.signals.notification_posted.emit(f"Paid ${cost:,} in severance for cancelling '{scene_title}'.")
                    self.signals.money_changed.emit(new_money)
            
            session.delete(scene_db)
            if commit:
                session.commit()
            if not silent:
                self.signals.notification_posted.emit(f"Scene '{scene_title}' has been deleted.")
            self.signals.scenes_changed.emit()
            return True
        except Exception as e:
            logger.error(f"Error deleting scene {scene_id}: {e}", exc_info=True)
            session.rollback()
            return False
        finally:
            session.close()
        
    def update_scene_full(self, scene_data: Scene) -> Dict:
        """
        Updates an entire scene record from a Scene dataclass.
        This is a more robust way for the UI to commit all its changes at once.
        """
        session = self.session_factory()
        try:
            scene_db = session.query(SceneDB).options(
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
            session.flush()

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
            
            session.commit()
            self.signals.scenes_changed.emit()
            return vp_id_map
        except Exception as e:
            logger.error(f"Error updating scene {scene_data.id}: {e}", exc_info=True)
            session.rollback()
            return {}
        finally:
            session.close()
        
    def start_editing_scene(self, scene_id: int, editing_tier_id: str) -> tuple[bool, int]:
        """Begins the editing process for a shot scene."""
        session = self.session_factory()
        try:
            scene_db = session.query(SceneDB).get(scene_id)
            if not scene_db or scene_db.status != 'shot':
                return False, 0

            editing_options = self.data_manager.post_production_data.get('editing_tiers', [])
            tier_data = next((t for t in editing_options if t['id'] == editing_tier_id), None)
            if not tier_data:
                return False, 0
            
            cost = tier_data.get('cost', 0)
            money_info = session.query(GameInfoDB).filter_by(key='money').one()
            current_money = int(float(money_info.value))

            new_money = current_money - cost
            money_info.value = str(new_money)
            scene_db.status = 'in_editing'
            scene_db.weeks_remaining = tier_data.get('weeks', 2)
            
            new_choices = scene_db.post_production_choices.copy() if scene_db.post_production_choices else {}
            new_choices['editing_tier'] = editing_tier_id
            scene_db.post_production_choices = new_choices
            flag_modified(scene_db, "post_production_choices")

            session.commit()
            self.signals.money_changed.emit(new_money)
            self.signals.notification_posted.emit(f"Editing started for '{scene_db.title}'. Cost: ${cost:,}")
            self.signals.scenes_changed.emit()
            return True, cost
        except Exception as e:
            logger.error(f"Error starting editing for scene {scene_id}: {e}", exc_info=True)
            session.rollback()
            return False, 0
        finally:
            session.close()

    def release_scene(self, scene_id: int) -> Dict:
        session = self.session_factory()
        try:
            scene_db = session.query(SceneDB).get(scene_id)
            if not (scene_db and scene_db.status == 'ready_to_release'):
                return {}
            # --- 1. GATHER DATA ---
            scene = scene_db.to_dataclass(Scene)
            talent_ids = list(scene.final_cast.values())
            cast_talents_db = session.query(TalentDB).filter(TalentDB.id.in_(talent_ids)).all()
            cast_talents_dc = [t.to_dataclass(Talent) for t in cast_talents_db]
            
            all_market_states = self.market_service.get_all_market_states()
            all_resolved_groups = self.market_service.get_all_resolved_group_data()

            # --- 2. DELEGATE CALCULATION ---
            revenue_result = self.revenue_calculator.calculate_revenue(
                scene, cast_talents_dc, all_market_states, all_resolved_groups
            )

            # --- 3. APPLY RESULTS ---
            revenue = revenue_result.total_revenue
            self.talent_command_service.update_popularity_from_scene(session, scene_id)  
    
            # Market Discovery Logic
            discovery_threshold = self.data_manager.game_config.get("market_discovery_interest_threshold", 1.5)
            num_to_discover = self.data_manager.game_config.get("market_discoveries_per_scene", 2)
    
            all_new_discoveries = DefaultDict(list)
            market_did_change = False
    
            for group_name, interest in revenue_result.viewer_group_interest.items():
                if interest < discovery_threshold:
                    continue
                    
                market_state_db = session.query(MarketGroupStateDB).get(group_name)
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
                market_state_db = session.query(MarketGroupStateDB).get(group_name)
                if market_state_db:
                    market_state_db.current_saturation = max(0, market_state_db.current_saturation - cost)
        
            scene_db.revenue = revenue
            scene_db.status = 'released'
            scene_db.viewer_group_interest = revenue_result.viewer_group_interest
            scene_db.revenue_modifier_details = revenue_result.revenue_modifier_details
    
            money_info = session.query(GameInfoDB).filter_by(key='money').one()
            new_money = int(float(money_info.value)) + revenue
            money_info.value = str(new_money)

            # Pass the email service in via __init__ and call it
            if discoveries := dict(all_new_discoveries):
                self.email_service.create_market_discovery_email(scene.title, discoveries, commit=False)

            session.commit()

            return {
                'discoveries': discoveries, 'revenue': revenue,
                'title': scene.title, 'new_money': new_money,
                'market_changed': market_did_change
            }
        except Exception as e:
            logger.error(f"Error releasing scene {scene_id}: {e}", exc_info=True)
            session.rollback()
            return {}
        finally:
            session.close()

    def shoot_scene(self, session: Session, scene_db: SceneDB) -> bool:
        """
        Begins shooting a scene. This is the entry point from TimeService.
        It checks for an interactive event. If one occurs, it signals the UI and
        returns True to pause the time advancement. Otherwise, it completes
        the shoot and returns False.
        This method operates within the transaction managed by TimeService.
        """
        # Ensure the dataclass is fully hydrated for the event check
        hydrated_scene_db = session.query(SceneDB).options(
            selectinload(SceneDB.virtual_performers),
            selectinload(SceneDB.action_segments).selectinload(ActionSegmentDB.slot_assignments),
            selectinload(SceneDB.cast)
        ).get(scene_db.id)
        scene_dc = hydrated_scene_db.to_dataclass(Scene)
        
        event_payload = self.event_service.check_for_shoot_event(session, scene_dc)

        if event_payload:
            # An event occurred. Emit signal and stop. Controller will resume.
            self.signals.interactive_event_triggered.emit(
                event_payload['event_data'],
                scene_dc.id,
                event_payload['talent_id']
            )
            return True # Indicates that an event has paused the process
        else:
            # No event. Proceed with the full shooting process.
            self._continue_shoot_scene(session, scene_dc.id, {})
            return False # Indicates the process completed normally

    def _continue_shoot_scene(self, session, scene_id: int, shoot_modifiers: Dict):
        """
        The second part of the shooting process, either called directly if
        no event occurs, or by the controller after an event is resolved.
        This method operates within a transaction managed by its caller.
        """
        scene_db = session.query(SceneDB).options(
            selectinload(SceneDB.cast)
        ).get(scene_id)
        
        if not scene_db:
            logger.error(f"[ERROR] _continue_shoot_scene: Scene ID {scene_id} not found.")
            return

        self.calculation_service.calculate_shoot_results(scene_db, shoot_modifiers)

    def process_weekly_post_production(self, session: Session) -> List[SceneDB]:
        """
        Updates weeks_remaining for scenes in editing and finalizes them if ready.
        Returns a list of scenes that finished editing this week.
        This method operates within the transaction managed by TimeService.
        """
        edited_scenes = []
        editing_scenes_db = session.query(SceneDB).filter_by(status='in_editing').all()
        for scene_db in editing_scenes_db:
            scene_db.weeks_remaining -= 1
            if scene_db.weeks_remaining <= 0:
                self.calculation_service.apply_post_production_effects(scene_db)
                edited_scenes.append(scene_db)
        return edited_scenes