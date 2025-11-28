import logging
import random
from typing import Dict, List, Any
from sqlalchemy.orm import selectinload, Session
from sqlalchemy.orm.attributes import flag_modified

from core.game_signals import GameSignals
from data.game_state import Scene, Talent
from data.data_manager import DataManager
from database.db_models import ( SceneDB, VirtualPerformerDB, ActionSegmentDB, SlotAssignmentDB,
                                TalentDB, GameInfoDB, ShootingBlocDB,
                                TalentChemistryDB, StudioStateDB )
from services.query.game_query_service import GameQueryService
from services.command.talent_command_service import TalentCommandService
from services.command.scene_processing_service import SceneProcessingService
from services.command.email_service import EmailService
from services.events.scene_event_trigger_service import SceneEventTriggerService
from services.market_service import MarketService
from services.calculation.revenue_calculator import RevenueCalculator
from services.calculation.bloc_cost_calculator import BlocCostCalculator
from services.calculation.crew_skill_calculator import CrewSkillCalculator

logger = logging.getLogger(__name__)

class SceneCommandService:
    """
    Command service for scene-related database operations.
    """
    
    def __init__(self, session_factory, signals: GameSignals, data_manager: DataManager, query_service: GameQueryService, 
             talent_command_service: TalentCommandService, market_service: MarketService, email_service: EmailService,
             scene_processing_service: SceneProcessingService, revenue_calculator: RevenueCalculator,
             scene_event_trigger_service: SceneEventTriggerService, bloc_cost_calculator: BlocCostCalculator,
             crew_skill_calculator: CrewSkillCalculator):
        self.session_factory = session_factory
        self.session_factory = session_factory
        self.signals = signals
        self.data_manager = data_manager
        self.query_service = query_service
        self.talent_command_service = talent_command_service
        self.market_service = market_service
        self.email_service = email_service
        self.scene_processing_service = scene_processing_service
        self.revenue_calculator = revenue_calculator
        self.scene_event_trigger_service = scene_event_trigger_service
        self.bloc_cost_calculator = bloc_cost_calculator
        self.crew_skill_calculator = crew_skill_calculator

    # --- CRUD and Logic Methods ---

    def _create_scene_for_bloc(self, session: Session, bloc_db: ShootingBlocDB) -> SceneDB:
        """Helper to create a scene within a bloc. Receives session from caller."""
        focus_target = self.data_manager.market_data.get('viewer_groups', [{}])[0].get('name', 'N/A')
        
        new_scene_db = SceneDB(
            title="Untitled Scene", status="design", focus_target=focus_target,
            scheduled_absolute_week=bloc_db.scheduled_absolute_week, bloc_id=bloc_db.id
        )
        
        default_vp_db = VirtualPerformerDB(name="Performer 1", gender="Female", ethnicity="Any")
        new_scene_db.virtual_performers.append(default_vp_db)
        
        session.add(new_scene_db)
        session.flush() 
        
        new_scene_db.title = f"Untitled Scene {new_scene_db.id}"
        return new_scene_db
    
    def create_shooting_bloc(self, 
                             scheduled_absolute_week: int,
                             num_scenes: int, 
                             name: str, 
                             logistics: Dict[str, str],
                             budget_data: Dict[str, Any]) -> bool:
        """
        Creates a new ShootingBloc and its associated blank scenes in the database.
        Arguments are now structured dictionaries from the ShootingBlocBuilder.
        """
        session = self.session_factory()
        try:
            # Unpack Logistics
            region_id = logistics.get("region_id", "south_west_us")
            location_id = logistics.get("location_id")
            visual_style_id = logistics.get("visual_style_id", "glossy")
            
            # Unpack Budget Data
            # Note: total_budget in budget_data is informational summation; actuals are in the sub-dicts
            budget_per_scene = budget_data.get("budget_per_scene", 0)
            camera_count = budget_data.get("camera_count", 1)
            
            # These are now separate maps
            department_budgets = budget_data.get("department_budgets", {})
            crew_assignments = budget_data.get("crew_assignments", {})
            
            studio_state = session.query(StudioStateDB).get(1)
            current_money = int(float(studio_state.money))

            cost = self.bloc_cost_calculator.calculate_shooting_bloc_cost(
                location_id=location_id,
                department_budgets=department_budgets,
                crew_assignments=crew_assignments,
                picture_set_settings={}, 
             )

            new_money = current_money - cost
            studio_state.money = str(new_money)

            # Generate Production Cache (RNG Rolls for Resources & Generic Crew)
            visual_style_def = self.data_manager.visual_styles.get(visual_style_id, {})
            
            production_cache = self.crew_skill_calculator.generate_production_cache(
                department_budgets=department_budgets,
                crew_assignments=crew_assignments,
                visual_style_def=visual_style_def,
                budget_per_scene=budget_per_scene,
                num_scenes=num_scenes,
                location_id=location_id
            )

            bloc_db = ShootingBlocDB(
                name=name, 
                scheduled_absolute_week=scheduled_absolute_week, 
                region_id=region_id,
                set_location_id=location_id, 
                visual_style_id=visual_style_id,
                budget_per_scene=budget_per_scene,
                camera_count=camera_count,
                department_budgets=department_budgets,
                crew_assignments=crew_assignments, 
                production_cache=production_cache,
                picture_set_settings={},
                production_cost=cost,
                current_momentum=50.0, # Start neutral
                current_stress=0.0     # Start fresh
            )

            session.add(bloc_db)
            session.flush()

            for _ in range(num_scenes):
                self._create_scene_for_bloc(session, bloc_db)
            
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

    def create_blank_scene(self, absolute_week: int) -> int:
        session = self.session_factory()
        try:
            focus_target = self.data_manager.market_data.get('viewer_groups', [{}])[0].get('name', 'N/A')
            
            new_scene_db = SceneDB(title="Untitled Scene", status="design", focus_target=focus_target,
                                   scheduled_absolute_week=absolute_week)
            
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

    def delete_scene(self, scene_id: int, penalty_percentage: float = 0.0) -> bool:
        session = self.session_factory()
        try:
            scene_db = session.query(SceneDB).options(selectinload(SceneDB.cast)).get(scene_id)
            if not scene_db: return False
            scene_title = scene_db.title
            
            if penalty_percentage > 0 and scene_db.cast:
                total_salary = sum(c.salary for c in scene_db.cast)
                cost = int(total_salary * penalty_percentage)
                if cost > 0:
                    studio_state = session.query(StudioStateDB).get(1)
                    current_money = int(float(studio_state.money))
                    new_money = current_money - cost
                    studio_state.money = str(new_money)
                    self.signals.notification_posted.emit(f"Paid ${cost:,} in severance for cancelling '{scene_title}'.")
                    self.signals.money_changed.emit(new_money)
            
            session.delete(scene_db)
            session.commit()
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

            for key in ['title', 'status', 'focus_target', 'total_runtime_minutes', 'scheduled_absolute_week', 'global_tags', 'is_locked', 'dom_sub_dynamic_level']:
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
            studio_state = session.query(StudioStateDB).get(1)
            current_money = int(float(studio_state.money))

            new_money = current_money - cost
            studio_state.money = str(new_money)
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
            cast_talents_db = session.query(TalentDB).options(
                selectinload(TalentDB.popularity_scores),
                selectinload(TalentDB.chemistry_a).joinedload(TalentChemistryDB.talent_b),
                selectinload(TalentDB.chemistry_b).joinedload(TalentChemistryDB.talent_a)
            ).filter(TalentDB.id.in_(talent_ids)).all()
            cast_talents_dc = [t.to_dataclass(Talent) for t in cast_talents_db]
            
            all_market_states = self.query_service.get_all_market_states()
            all_resolved_groups = self.market_service.get_all_resolved_group_data()

            # --- 2. DELEGATE CALCULATION ---
            revenue_result = self.revenue_calculator.calculate_revenue(
                scene, cast_talents_dc, all_market_states, all_resolved_groups
            )

            # --- 3. APPLY RESULTS ---
            revenue = revenue_result.total_revenue
            self.talent_command_service.update_popularity_from_scene(session, scene_id)  
    
            discoveries = self.market_service.process_discoveries_from_release(
                session, scene, revenue_result.viewer_group_interest
            )
            market_did_change = bool(discoveries)
            
            self.market_service.update_saturation_from_release(
                session, revenue_result.market_saturation_updates
            )
        
            scene_db.revenue = revenue
            scene_db.status = 'released'
            scene_db.viewer_group_interest = revenue_result.viewer_group_interest
            scene_db.revenue_modifier_details = revenue_result.revenue_modifier_details
    
            studio_state = session.query(StudioStateDB).get(1)
            new_money = int(float(studio_state.money)) + revenue
            studio_state.money = str(new_money)

            if discoveries:
                abs_week_info = session.query(GameInfoDB).filter_by(key='absolute_week').one()
                current_absolute_week = int(abs_week_info.value)
                self.email_service.create_market_discovery_email(session, scene.title, discoveries, current_absolute_week)

            session.commit()
            if discoveries:
                self.signals.emails_changed.emit()

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
        """
        hydrated_scene_db = session.query(SceneDB).options(
            selectinload(SceneDB.virtual_performers),
            selectinload(SceneDB.action_segments).selectinload(ActionSegmentDB.slot_assignments),
            selectinload(SceneDB.cast)
        ).get(scene_db.id)
        scene_dc = hydrated_scene_db.to_dataclass(Scene)
        
        event_payload = self.scene_event_trigger_service.check_for_shoot_event(session, scene_dc)

        if event_payload:
            self.signals.interactive_event_triggered.emit(
                event_payload['event_data'],
                scene_dc.id,
                event_payload['talent_id']
            )
            return True 
        else:
            self._continue_shoot_scene(session, scene_dc.id, {})
            return False
        
    def continue_shoot_scene_after_event(self, scene_id: int, shoot_modifiers: Dict) -> bool:
        """Public method to continue shooting after event resolution."""
        session = self.session_factory()
        try:
            self._continue_shoot_scene(session, scene_id, shoot_modifiers)
            session.commit()
            return True
        except Exception as e:
            logger.error(f"Error continuing shoot for scene {scene_id}: {e}", exc_info=True)
            session.rollback()
            return False
        finally:
            session.close()

    def _continue_shoot_scene(self, session, scene_id: int, shoot_modifiers: Dict):
        """
        The second part of the shooting process.
        """
        scene_db = session.query(SceneDB).options(
            selectinload(SceneDB.cast)
        ).get(scene_id)
        
        if not scene_db:
            logger.error(f"[ERROR] _continue_shoot_scene: Scene ID {scene_id} not found.")
            return

        self.scene_processing_service.prepare_for_shoot_calculation(session, scene_db)
        shoot_result = self.scene_processing_service.run_shoot_calculations(session, scene_db, shoot_modifiers)
        self.scene_processing_service.apply_shoot_calculation_results(session, scene_db, shoot_result)

    def process_weekly_post_production(self, session: Session) -> List[SceneDB]:
        """
        Updates weeks_remaining for scenes in editing and finalizes them if ready.
        """
        edited_scenes = []
        editing_scenes_db = session.query(SceneDB).filter_by(status='in_editing').all()
        for scene_db in editing_scenes_db:
            scene_db.weeks_remaining -= 1
            if scene_db.weeks_remaining <= 0:
                self.scene_processing_service.apply_post_production_effects(session, scene_db)
                edited_scenes.append(scene_db)
        return edited_scenes