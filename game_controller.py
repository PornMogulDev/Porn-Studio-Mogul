import copy
import json
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QDialog
import random
from sqlalchemy.orm import joinedload
from sqlalchemy import func

from interfaces import IGameController, GameSignals
from typing import runtime_checkable
from game_state import *
from save_manager import SaveManager, QUICKSAVE_NAME, EXITSAVE_NAME
from talent_generator import TalentGenerator
from data_manager import DataManager
from settings_manager import SettingsManager 
from database.db_models import *

from services.market_service import MarketService
from services.talent_service import TalentService
from services.scene_service import SceneService
from services.time_service import TimeService
from services.go_to_list_service import GoToListService

class GameController(QObject):
    def __init__(self, settings_manager: SettingsManager, data_manager: DataManager):
        super().__init__()
        self.settings_manager = settings_manager
        self.data_manager = data_manager
        self.game_state = GameState() 
        self.save_manager = SaveManager()
        self.signals = GameSignals()
        
        self.db_session = None
        self.current_save_path = None 
        
        self.game_constant = self.data_manager.game_config
        self.tag_definitions = self.data_manager.tag_definitions
        self.market_data = self.data_manager.market_data
        self.affinity_data = self.data_manager.affinity_data
        self.generator_data = self.data_manager.generator_data
        self.talent_archetypes = self.data_manager.talent_archetypes
        
        self.talent_generator = TalentGenerator(self.generator_data, self.affinity_data, self.tag_definitions, self.talent_archetypes)

        self.market_service = None
        self.talent_service = None
        self.scene_service = None
        self.time_service = None
        self.go_to_list_service = None # Add the new service attribute
        
        self._cached_style_tags_data = None
        self._cached_action_tags_data = None
        self._favorite_tags_cache = {}

        self._available_ethnicities = None
        self.game_over = False

    def get_available_ethnicities(self) -> list[str]:
        if self._available_ethnicities is None:
            self._available_ethnicities = ["Any"] + sorted([e['name'] for e in self.generator_data.get('ethnicities', [])])
        return self._available_ethnicities

    def get_available_boob_cups(self) -> list[str]:
        return [b['name'] for b in self.generator_data.get('boob_cups', [])]

    # --- UI Data Access Methods ---
    def get_filtered_talents(self, filters: dict) -> List[Talent]:
        if not self.talent_service: return []
        return self.talent_service.get_filtered_talents(filters)
    
    def get_blocs_for_schedule_view(self, year: int) -> List[ShootingBloc]:
        if not self.scene_service: return []
        return self.scene_service.get_blocs_for_schedule_view(year)

    def get_bloc_by_id(self, bloc_id: int) -> Optional[ShootingBloc]:
        if not self.scene_service: return None
        return self.scene_service.get_bloc_by_id(bloc_id)

    def get_scene_for_planner(self, scene_id: int) -> Optional[Scene]:
        if not self.scene_service: return None
        return self.scene_service.get_scene_for_planner(scene_id)
        
    def get_shot_scenes(self) -> List[Scene]:
        if not self.scene_service: return []
        return self.scene_service.get_shot_scenes()
        
    def get_all_market_states(self) -> Dict[str, MarketGroupState]:
        if not self.market_service: return {}
        return self.market_service.get_all_market_states()
        
    def get_scene_history_for_talent(self, talent_id: int) -> List[Scene]:
        if not self.scene_service: return []
        return self.scene_service.get_scene_history_for_talent(talent_id)

    def get_castable_scenes(self) -> List[Dict]:
        """Gets a simplified list of scenes in 'casting' for UI filters."""
        if not self.scene_service: return []
        return self.scene_service.get_castable_scenes_for_ui()

    def get_uncast_roles_for_scene(self, scene_id: int) -> List[Dict]:
        """Gets a list of uncast roles for a specific scene for UI filters."""
        if not self.scene_service: return []
        return self.scene_service.get_uncast_roles_for_scene_ui(scene_id)

    # --- Go-To List Data Access (Proxy Methods) ---
    def get_go_to_list_talents(self) -> List[Talent]:
        """Gets all unique talents present in any Go-To List category."""
        if not self.db_session: return []
        # This one is a bit different as it queries assignments but returns talents
        assigned_talent_ids_query = self.db_session.query(GoToListAssignmentDB.talent_id).distinct()
        talent_ids_tuples = assigned_talent_ids_query.all()
        if not talent_ids_tuples: return []
        talent_ids = [item[0] for item in talent_ids_tuples]
        talents_db = self.db_session.query(TalentDB).filter(TalentDB.id.in_(talent_ids)).order_by(TalentDB.alias).all()
        return [t.to_dataclass(Talent) for t in talents_db]
    
    def get_go_to_list_categories(self) -> List[Dict]:
        if not self.go_to_list_service: return []
        return self.go_to_list_service.get_all_categories()

    def get_talents_in_go_to_category(self, category_id: int) -> List[Talent]:
        if not self.go_to_list_service: return []
        return self.go_to_list_service.get_talents_in_category(category_id)

    def get_talent_go_to_categories(self, talent_id: int) -> List[Dict]:
        if not self.go_to_list_service: return []
        return self.go_to_list_service.get_talent_categories(talent_id)

    def get_all_emails(self) -> List[EmailMessage]:
        if not self.db_session: return []
        emails_db = self.db_session.query(EmailMessageDB).order_by(EmailMessageDB.year.desc(), EmailMessageDB.week.desc(), EmailMessageDB.id.desc()).all()
        return [e.to_dataclass(EmailMessage) for e in emails_db]

    # --- Game Logic ---
    def advance_week(self):
        if self.game_over: return

        # Pre-flight check for incomplete scenes scheduled for this week
        incomplete_scenes = self.scene_service.get_incomplete_scenes_for_week(
            self.game_state.week, self.game_state.year
        )
        if incomplete_scenes:
            self.signals.incomplete_scene_check_requested.emit(incomplete_scenes)
            return # Stop here, wait for UI to handle and possibly recall this method

        self.save_manager.auto_save(self.db_session)
        # After auto_save, the session is rebound, so we need to get it again
        self.db_session = self.save_manager.db_manager.get_session()
        self._reinitialize_services() # Re-init services with the new session

        changes = self.time_service.process_week_advancement()
        
        # Update GameState money from DB before emitting signals
        money_info = self.db_session.query(GameInfoDB).filter_by(key='money').one()
        # --- FIX: Robust parsing of money value ---
        self.game_state.money = int(float(money_info.value))

        self.db_session.commit()

        if changes.get("paused"): # If the week was paused by an event, don't emit final signals yet
            if changes["scenes"]: self.signals.scenes_changed.emit()
            return

        if changes["scenes"]: self.signals.scenes_changed.emit()
        if changes["market"]: self.signals.market_changed.emit()
        if changes["talent_pool"]: self.signals.talent_pool_changed.emit()

        if self.game_state.money <= self.game_constant.get('game_over_threshold', -5000):
            self.signals.game_over_triggered.emit("bankruptcy"); return

        self.signals.time_changed.emit(self.game_state.week, self.game_state.year)
        self.signals.money_changed.emit(self.game_state.money)

    def start_editing_scene(self, scene_id: int, editing_tier_id: str):
        """Starts the editing process for a shot scene."""
        if self.scene_service.start_editing_scene(scene_id, editing_tier_id):
            self.db_session.commit()
        else:
            # The service sends its own notification on failure (e.g., not enough money)
            self.db_session.rollback()

    def release_scene(self, scene_id: int):
        self.scene_service.release_scene(scene_id)
        self.db_session.commit()
    
    def create_shooting_bloc(self, week: int, year: int, num_scenes: int, settings: Dict[str, str], name: str, policies: List[str]) -> bool:
        """
        Calculates the cost authoritatively and creates a shooting bloc.
        This version does NOT accept a 'cost' parameter from the UI.
        """
        if not self.scene_service: return False

        # --- Authoritative server-side cost calculation ---
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
            if category in ["Camera Equipment", "Camera Setup"]:
                continue
            tiers = self.data_manager.production_settings_data.get(category, [])
            tier_info = next((t for t in tiers if t['tier_name'] == tier_name), None)
            if tier_info:
                total_cost_per_scene += tier_info.get('cost_per_scene', 0)
        
        settings_cost = total_cost_per_scene * num_scenes

        # Cost from policies (per bloc)
        policies_cost = 0
        for policy_id in policies:
            if policy_data := self.data_manager.on_set_policies_data.get(policy_id):
                policies_cost += policy_data.get('cost_per_bloc', 0)
        
        final_cost = int(settings_cost + policies_cost) # Ensure final cost is an integer
        
        if self.game_state.money < final_cost:
            self.signals.notification_posted.emit(f"Not enough money. Cost: ${final_cost:,}, Have: ${self.game_state.money:,}")
            return False
        
        # Deduct money and create the bloc
        money_info = self.db_session.query(GameInfoDB).filter_by(key='money').one()
        self.game_state.money = int(float(money_info.value)) - final_cost
        money_info.value = str(self.game_state.money)

        final_name = name.strip() if name.strip() else f"{year} W{week} Shoot"
        
        # Call the service with the correctly calculated cost and argument order
        bloc_id = self.scene_service.create_shooting_bloc(week, year, num_scenes, settings, final_cost, final_name, policies)

        if bloc_id:
            self.db_session.commit()
            self.signals.notification_posted.emit(f"Shooting bloc '{final_name}' planned. Cost: ${final_cost:,}")
            self.signals.money_changed.emit(self.game_state.money)
            self.signals.scenes_changed.emit()
            return True
        else:
            self.db_session.rollback()
            # Restore money state if it failed
            current_money = int(float(money_info.value)) + final_cost
            self.game_state.money = current_money
            money_info.value = str(current_money)
            self.signals.notification_posted.emit("Error: Failed to plan shooting bloc.")
            return False

    def create_blank_scene(self, week: Optional[int] = None, year: Optional[int] = None) -> int:
        use_week = week if week is not None else self.game_state.week
        use_year = year if year is not None else self.game_state.year
        new_id = self.scene_service.create_blank_scene(use_week, use_year)
        self.db_session.commit()
        return new_id

    def delete_scene(self, scene_id: int, silent: bool = False, penalty_percentage: float = 0.0, commit_session: bool = True): 
        deleted_title = self.scene_service.delete_scene(scene_id, penalty_percentage)
        if deleted_title:
            if commit_session:
                self.db_session.commit()
            if not silent:
                 self.signals.notification_posted.emit(f"Scene '{deleted_title}' has been deleted.")
            self.signals.scenes_changed.emit()
        return deleted_title

    def update_scene_full(self, scene_data: Scene):
        """Receives a full Scene dataclass from the presenter and updates the database."""
        self.scene_service.update_scene_full(scene_data)
        self.db_session.commit()

    def calculate_talent_demand(self, talent_id: int, scene_id: int, vp_id: int) -> int:
        return self.talent_service.calculate_talent_demand(talent_id, scene_id, vp_id)

    def cast_talent_for_virtual_performer(self, talent_id: int, scene_id: int, virtual_performer_id: int, cost: int):
        result = self.scene_service.cast_talent_for_role(talent_id, scene_id, virtual_performer_id, cost)
        
        if result:
            self.db_session.commit()
            self.signals.notification_posted.emit(result['main_message'])
            if result['locked_message']: self.signals.notification_posted.emit(result['locked_message'])
            if result['complete_message']: self.signals.notification_posted.emit(result['complete_message'])
            self.signals.scenes_changed.emit()
        else: # Revert if something went wrong
             self.db_session.rollback()

    def cast_talent_for_multiple_roles(self, talent_id: int, roles: List[Dict]):
        """Casts a single talent into multiple roles across different scenes."""
        talent = self.talent_service.get_talent_by_id(talent_id)
        if not talent:
            self.signals.notification_posted.emit("Error: Talent not found.")
            return

        all_messages = []
        scenes_affected = set()

        # Server-side validation as a safeguard against client-side errors or other entry points
        scene_ids = [role['scene_id'] for role in roles]
        if len(scene_ids) != len(set(scene_ids)):
            self.db_session.rollback()
            self.signals.notification_posted.emit("Casting failed: Cannot assign a talent to multiple roles in the same scene.")
            return

        for role in roles:
            scene_id = role['scene_id']
            virtual_performer_id = role['virtual_performer_id']
            cost = role['cost']
            
            result = self.scene_service.cast_talent_for_role(talent_id, scene_id, virtual_performer_id, cost)
            
            if result:
                all_messages.append(result['main_message'])
                if result['locked_message']: all_messages.append(result['locked_message'])
                if result['complete_message']: all_messages.append(result['complete_message'])
                scenes_affected.add(scene_id)
            else:
                self.db_session.rollback()
                self.signals.notification_posted.emit(f"An error occurred while casting {talent.alias}. Operation cancelled.")
                return

        self.db_session.commit()
        
        for msg in all_messages:
            self.signals.notification_posted.emit(msg)
        
        if scenes_affected:
            self.signals.scenes_changed.emit()

    def get_style_tags_for_planner(self) -> Tuple[List[Dict], Set[str], Set[str]]:
        if self._cached_style_tags_data: return self._cached_style_tags_data
        style_tags, tag_categories, style_tag_orientations = [], set(), set()
        for full_name, tag_data in self.tag_definitions.items():
            if tag_data.get('type') in ['Global', 'Assigned']:
                cats_raw = tag_data.get('categories', []); cats = [cats_raw] if isinstance(cats_raw, str) else cats_raw
                tag_categories.update(cats)
                if orientation := tag_data.get('orientation'): style_tag_orientations.add(orientation)
                tag_data_with_name = tag_data.copy(); tag_data_with_name['full_name'] = full_name
                style_tags.append(tag_data_with_name)
        self._cached_style_tags_data = (style_tags, tag_categories, style_tag_orientations)
        return self._cached_style_tags_data

    def get_action_tags_for_planner(self) -> Tuple[List[Dict], Set[str], Set[str]]:
        if self._cached_action_tags_data: return self._cached_action_tags_data
        action_tags, action_tag_categories, action_tag_orientations = [], set(), set()
        for full_name, tag_data in self.tag_definitions.items():
            if tag_data.get('type') == 'Action':
                cats_raw = tag_data.get('categories', []); cats = [cats_raw] if isinstance(cats_raw, str) else cats_raw
                action_tag_categories.update(cats)
                if orientation := tag_data.get('orientation'): action_tag_orientations.add(orientation)
                tag_data_with_name = tag_data.copy(); tag_data_with_name['full_name'] = full_name
                count = sum(slot.get('count', slot.get('min_count', 0)) for slot in tag_data.get('slots', []))
                tag_data_with_name['participant_count'] = count
                action_tags.append(tag_data_with_name)
        self._cached_action_tags_data = (action_tags, action_tag_categories, action_tag_orientations)
        return self._cached_action_tags_data

    def get_resolved_group_data(self, group_name: str) -> Dict: return self.market_service.get_resolved_group_data(group_name)
    
    def resolve_interactive_event(self, event_id: str, scene_id: int, talent_id: int, choice_id: str):
        """
        Applies the effects of a player's choice from an interactive event
        and resumes the scene shooting process.
        """
        if not self.scene_service: return

        event_data = self.data_manager.scene_events.get(event_id)
        if not event_data:
            print(f"[ERROR] Could not find event data for id: {event_id}")
            self.scene_service._continue_shoot_scene(scene_id, {}) # Continue shoot even if event is broken
            return

        choice_data = next((c for c in event_data.get('choices', []) if c.get('id') == choice_id), None)
        if not choice_data:
            print(f"[ERROR] Could not find choice data for id: {choice_id} in event {event_id}")
            self.scene_service._continue_shoot_scene(scene_id, {})
            return
        
        shoot_modifiers = defaultdict(lambda: defaultdict(dict))
        scene_was_cancelled = False
        other_talent_id = None
        other_talent_name = None
        
        effects = choice_data.get('effects', []) or [] # Ensure it's a list
        talent = self.talent_service.get_talent_by_id(talent_id)
        scene_db = self.db_session.query(SceneDB).options(joinedload(SceneDB.cast)).get(scene_id)

        # Pre-process effects to find and resolve special targets like 'other_talent_in_scene'
        needs_other_talent = any(eff.get('target') == 'other_talent_in_scene' for eff in effects)
        if needs_other_talent and scene_db:
            cast_ids = [c.talent_id for c in scene_db.cast if c.talent_id != talent_id]
            if cast_ids:
                other_talent_id = random.choice(cast_ids)
                other_talent_db = self.db_session.query(TalentDB.alias).filter_by(id=other_talent_id).one_or_none()
                if other_talent_db:
                    other_talent_name = other_talent_db.alias
        
        # --- NEW: Helper function to apply a list of effects ---
        def apply_effects(effects_list: List[Dict], current_modifiers: Dict) -> bool:
            nonlocal scene_was_cancelled # Allow modification of the outer scope variable
            for effect in effects_list:
                effect_type = effect.get('type')
                if effect_type == 'add_cost':
                    cost = effect.get('amount', 0)
                    if self.game_state.money >= cost:
                        money_info = self.db_session.query(GameInfoDB).filter_by(key='money').one()
                        self.game_state.money -= cost
                        money_info.value = str(int(self.game_state.money))
                        self.signals.money_changed.emit(self.game_state.money)
                elif effect_type == 'notification':
                    message = effect.get('message', '...')
                    if talent: message = message.replace('{talent_name}', talent.alias)
                    if other_talent_name: message = message.replace('{other_talent_name}', other_talent_name)
                    if scene_db: message = message.replace('{scene_title}', scene_db.title)
                    self.signals.notification_posted.emit(message)
                elif effect_type == 'cancel_scene':
                    if not scene_db: continue
                    total_salary_cost = sum(c.salary for c in scene_db.cast)
                    money_info = self.db_session.query(GameInfoDB).filter_by(key='money').one()
                    self.game_state.money -= total_salary_cost
                    money_info.value = str(int(self.game_state.money))
                    self.signals.money_changed.emit(self.game_state.money)
                    deleted_title = self.delete_scene(scene_id, silent=True, commit_session=False)
                    if deleted_title:
                        scene_was_cancelled = True
                        reason = effect.get('reason', 'Event')
                        self.signals.notification_posted.emit(f"Scene '{deleted_title}' cancelled ({reason}). Lost salary costs of ${total_salary_cost:,}.")
                elif effect_type in ('modify_performer_contribution', 'modify_performer_contribution_random'):
                    target_talent_id = talent_id if effect.get('target') == 'triggering_talent' else other_talent_id
                    if target_talent_id:
                        reason = effect.get('reason', 'Event')
                        if effect_type == 'modify_performer_contribution':
                            current_modifiers['performer_mods'][target_talent_id] = {'modifier': effect.get('modifier', 1.0), 'reason': reason}
                        else:
                            current_modifiers['performer_mods'][target_talent_id] = {'min_mod': effect.get('min_mod', 1.0), 'max_mod': effect.get('max_mod', 1.0), 'reason': reason}
                elif effect_type == 'modify_scene_quality':
                    current_modifiers['quality_mods']['overall'] = {'modifier': effect.get('modifier', 1.0), 'reason': effect.get('reason', 'Event')}
                
                # --- NEW LOGIC: Chained Event ---
                elif effect_type == 'trigger_event':
                    new_event_id = effect.get('event_id')
                    new_event_data = self.data_manager.scene_events.get(new_event_id)
                    if new_event_data:
                        self.signals.interactive_event_triggered.emit(new_event_data, scene_id, talent_id)
                        return True # Stop processing, a new event is taking over
                    else:
                        print(f"[ERROR] Chained event error: Could not find event with id '{new_event_id}'")
                
                # --- NEW LOGIC: Randomized Outcome ---
                elif effect_type == 'random_outcome':
                    outcomes = effect.get('outcomes', [])
                    if outcomes:
                        weights = [o.get('chance', 1.0) for o in outcomes]
                        chosen_outcome = random.choices(outcomes, weights=weights, k=1)[0]
                        if apply_effects(chosen_outcome.get('effects', []), current_modifiers):
                             return True # Propagate the stop signal
            return False # Continue processing

        if apply_effects(effects, shoot_modifiers):
            self.db_session.commit()
            return # A chained event was triggered, so we stop here.

        # --- Original logic to continue the shoot ---
        if not scene_was_cancelled:
            self.scene_service._continue_shoot_scene(scene_id, shoot_modifiers)

        self.db_session.commit()
        
        # After resolving the event, automatically try to continue the week.
        self.advance_week()

    def _reinitialize_services(self):
        self._favorite_tags_cache = {}
        if not self.db_session:
            return
        self.market_service = MarketService(self.db_session, self.data_manager)
        self.talent_service = TalentService(self.db_session, self.data_manager, self.market_service)
        self.scene_service = SceneService(self.db_session, self.signals, self.data_manager, self.talent_service, self.market_service)
        self.time_service = TimeService(self.db_session, self.game_state, self.signals, self.scene_service, self.talent_service, self.market_service, self.data_manager)
        self.go_to_list_service = GoToListService(self.db_session, self.signals) # Instantiate the new service

    def new_game_started(self):
        if self.db_session:
            self.db_session.close()
            self.db_session = None
        self.save_manager.db_manager.disconnect()
        self._favorite_tags_cache = {}

        from save_manager import LIVE_SESSION_NAME
        self.current_save_path = self.save_manager.create_new_save_db(LIVE_SESSION_NAME)
        
        self.db_session = self.save_manager.db_manager.get_session()

        self.game_state = GameState(week=1, year=self.game_constant["starting_year"], money=self.game_constant["initial_money"])
        game_info_data = [
            GameInfoDB(key='week', value=str(self.game_state.week)),
            GameInfoDB(key='year', value=str(self.game_state.year)),
            GameInfoDB(key='money', value=str(self.game_state.money))
        ]
        self.db_session.add_all(game_info_data)

        all_group_names = [g['name'] for g in self.market_data.get('viewer_groups', [])]
        for group in self.market_data.get('viewer_groups', []):
            if name := group.get('name'):
                market_state = MarketGroupState(name=name)
                self.db_session.add(MarketGroupStateDB.from_dataclass(market_state))
        
        initial_talents = self.talent_generator.generate_multiple_talents(100, start_id=1)
        for talent in initial_talents:
            for name in all_group_names: talent.popularity[name] = 0.0
            self.db_session.add(TalentDB.from_dataclass(talent))

        # Create the default, non-deletable "General" Go-To List category
        general_category = GoToListCategoryDB(name="General", is_deletable=False)
        self.db_session.add(general_category)

        self.db_session.commit()

        self._reinitialize_services()
        self.create_email("Welcome to the Studio!", "Welcome to your new studio! Your goal is to become a successful producer.\n\nDesign scenes, cast talent, and make a profit!\n\nGood luck!")
        self.signals.money_changed.emit(self.game_state.money)
        self.signals.time_changed.emit(self.game_state.week, self.game_state.year)
        self.signals.talent_pool_changed.emit()
        self.signals.new_game_started.emit()
        self.signals.show_main_window_requested.emit()
        
    def handle_game_over(self): self.game_over = True; self.signals.show_start_screen_requested.emit()
    def save_game(self, save_name='autosave'):
        if self.db_session and self.current_save_path:
            self.db_session.commit() 
            self.save_manager.copy_save(self.current_save_path, save_name)
            self.signals.saves_changed.emit() # Notify UI that the list of saves has changed

    def load_game(self, save_name):
        from save_manager import LIVE_SESSION_NAME
        if self.db_session: self.db_session.close()
        self._favorite_tags_cache = {}
        
        # load_game now copies the save to the live session file and connects to it.
        # It returns a GameState with only week, year, money.
        self.game_state = self.save_manager.load_game(save_name)
        
        # The current path is now always the live session path.
        self.current_save_path = str(self.save_manager.get_save_path(LIVE_SESSION_NAME))
        self.db_session = self.save_manager.db_manager.get_session()
        
        self._reinitialize_services()
        self.signals.money_changed.emit(self.game_state.money)
        self.signals.time_changed.emit(self.game_state.week, self.game_state.year)
        self.signals.scenes_changed.emit(); self.signals.talent_pool_changed.emit(); self.signals.emails_changed.emit()
        self.signals.show_main_window_requested.emit()

    def delete_save_file(self, save_name: str) -> bool:
        if self.save_manager.delete_save(save_name): 
            self.signals.saves_changed.emit(); return True
        return False

    def continue_game(self): self.load_game(self.save_manager.load_latest_save())
    def quick_save(self): self.save_game(QUICKSAVE_NAME); self.signals.notification_posted.emit("Game quick saved!")
    def quick_load(self):
        if self.save_manager.quick_load_exists(): self.load_game(QUICKSAVE_NAME); self.signals.notification_posted.emit("Game quick loaded!")
        else: self.signals.notification_posted.emit("No quick save found!")

    def check_for_saves(self) -> bool: return self.save_manager.has_saves()
    def return_to_main_menu(self, exit_save):
        if self.game_over: self.signals.show_start_screen_requested.emit(); return
        if exit_save: self.save_game(EXITSAVE_NAME)
        if self.db_session: self.db_session.close(); self.db_session = None
        self.save_manager.db_manager.disconnect() # Fully disconnect engine
        self.signals.show_start_screen_requested.emit()

    def quit_game(self, exit_save=False):
        if exit_save: self.save_game(EXITSAVE_NAME)
        self.signals.quit_game_requested.emit()

    def create_email(self, subject: str, body: str):
        new_email = EmailMessageDB(subject=subject, body=body, week=self.game_state.week, year=self.game_state.year, is_read=False)
        self.db_session.add(new_email)
        self.db_session.commit()
        self.signals.emails_changed.emit()

    def get_unread_email_count(self) -> int:
        if not self.db_session: return 0
        return self.db_session.query(EmailMessageDB).filter_by(is_read=False).count()

    def mark_email_as_read(self, email_id: int):
        email_db = self.db_session.query(EmailMessageDB).get(email_id)
        if email_db and not email_db.is_read:
            email_db.is_read = True
            self.db_session.commit()
            self.signals.emails_changed.emit()

    def delete_emails(self, email_ids: list[int]):
        if not self.db_session or not email_ids: return
        self.db_session.query(EmailMessageDB).filter(EmailMessageDB.id.in_(email_ids)).delete(synchronize_session=False)
        self.db_session.commit()
        self.signals.emails_changed.emit()
    
    # --- Go-To List Actions (Proxy Methods) ---
    def add_talent_to_go_to_list(self, talent_id: int):
        """Adds a talent to the default 'General' Go-To List category."""
        if not self.db_session: return
        
        general_category = self.db_session.query(GoToListCategoryDB).filter_by(name="General").one_or_none()
        if not general_category:
            self.signals.notification_posted.emit("Error: 'General' Go-To category not found.")
            return

        if self.go_to_list_service.add_talent_to_category(talent_id, general_category.id):
            self.db_session.commit()
            self.signals.go_to_list_changed.emit()
        else:
            self.db_session.rollback()

    def remove_talents_from_go_to_list(self, talent_ids: list[int]):
        """Removes talents from ALL Go-To List categories."""
        if not self.db_session or not talent_ids: return
        num_deleted = self.db_session.query(GoToListAssignmentDB).filter(
            GoToListAssignmentDB.talent_id.in_(talent_ids)
        ).delete(synchronize_session=False)
        
        if num_deleted > 0:
            self.db_session.commit()
            self.signals.notification_posted.emit(f"Removed selected talent(s) from all Go-To categories.")
            self.signals.go_to_list_changed.emit()

    def create_go_to_list_category(self, name: str):
        if not self.go_to_list_service: return
        if self.go_to_list_service.create_category(name):
            self.db_session.commit()
            self.signals.go_to_categories_changed.emit()
        else:
            self.db_session.rollback()

    def rename_go_to_list_category(self, category_id: int, new_name: str):
        if not self.go_to_list_service: return
        if self.go_to_list_service.rename_category(category_id, new_name):
            self.db_session.commit()
            self.signals.go_to_categories_changed.emit()
        else:
            self.db_session.rollback()

    def delete_go_to_list_category(self, category_id: int):
        if not self.go_to_list_service: return
        if self.go_to_list_service.delete_category(category_id):
            self.db_session.commit()
            self.signals.go_to_categories_changed.emit()
            self.signals.go_to_list_changed.emit() # Deleting a category affects assignments
        else:
            self.db_session.rollback()

    def add_talent_to_go_to_category(self, talent_id: int, category_id: int):
        if not self.go_to_list_service: return
        if self.go_to_list_service.add_talent_to_category(talent_id, category_id):
            self.db_session.commit()
            self.signals.go_to_list_changed.emit()
        else:
            self.db_session.rollback()

    # --- NEW METHOD ---
    def add_talents_to_go_to_category(self, talent_ids: list[int], category_id: int):
        if not self.go_to_list_service: return
        num_added = self.go_to_list_service.add_talents_to_category(talent_ids, category_id)
        if num_added > 0:
            self.db_session.commit()
            self.signals.go_to_list_changed.emit()
        else:
            # Rollback even if 0 were added in case of other session changes
            self.db_session.rollback()

    def remove_talent_from_go_to_category(self, talent_id: int, category_id: int):
        if not self.go_to_list_service: return
        if self.go_to_list_service.remove_talent_from_category(talent_id, category_id):
            self.db_session.commit()
            self.signals.go_to_list_changed.emit()
        else:
            self.db_session.rollback()

    def remove_talents_from_go_to_category(self, talent_ids: list[int], category_id: int):
        if not self.go_to_list_service: return
        num_deleted = self.go_to_list_service.remove_talents_from_category(talent_ids, category_id)
        if num_deleted > 0:
            self.db_session.commit()
            self.signals.go_to_list_changed.emit()
        else:
            # Rollback even if 0 were deleted in case of other session changes
            self.db_session.rollback()
    
    # --- Tag Favorites System ---
    def _get_favorites(self, tag_type: str) -> List[str]:
        key = f"favorite_{tag_type}_tags"
        if key in self._favorite_tags_cache:
            return self._favorite_tags_cache[key]
        
        if not self.db_session: return []
        fav_info = self.db_session.query(GameInfoDB).filter_by(key=key).first()
        if fav_info and fav_info.value:
            try:
                favs = json.loads(fav_info.value)
                self._favorite_tags_cache[key] = favs
                return favs
            except (json.JSONDecodeError, TypeError):
                pass
        
        self._favorite_tags_cache[key] = []
        return []

    def _set_favorites(self, tag_type: str, favs_list: List[str]):
        key = f"favorite_{tag_type}_tags"
        if not self.db_session: return

        fav_info = self.db_session.query(GameInfoDB).filter_by(key=key).first()
        json_val = json.dumps(sorted(favs_list))

        if not fav_info:
            fav_info = GameInfoDB(key=key, value=json_val)
            self.db_session.add(fav_info)
        else:
            fav_info.value = json_val
        
        self._favorite_tags_cache[key] = sorted(favs_list)
        self.db_session.commit()
        self.signals.favorites_changed.emit()

    def get_favorite_tags(self, tag_type: str) -> List[str]:
        return self._get_favorites(tag_type)

    def toggle_favorite_tag(self, tag_name: str, tag_type: str):
        current_favs = self._get_favorites(tag_type).copy()
        if tag_name in current_favs:
            current_favs.remove(tag_name)
        else:
            current_favs.append(tag_name)
        self._set_favorites(tag_type, current_favs)

    def reset_favorite_tags(self, tag_type: str):
        self._set_favorites(tag_type, [])