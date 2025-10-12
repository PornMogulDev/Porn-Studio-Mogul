import logging
import random
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from sqlalchemy.orm import joinedload

from game_state import Scene, Talent
from data_manager import DataManager
from services.talent_service import TalentService
from interfaces import GameSignals
from database.db_models import TalentDB, ShootingBlocDB, GameInfoDB, SceneDB, SceneCastDB

if TYPE_CHECKING:
    from services.scene_service import SceneService

logger = logging.getLogger(__name__)

class SceneEventService:
    """
    Handles the triggering and resolution of interactive events that occur during scene shoots.
    """
    def __init__(self, db_session, game_state, signals: GameSignals, data_manager: DataManager, 
                 talent_service: TalentService):
        self.session = db_session
        self.game_state = game_state
        self.signals = signals
        self.data_manager = data_manager
        self.talent_service = talent_service

    # --- Methods Moved from SceneCalculationService (Event Triggering) ---

    def check_for_shoot_event(self, scene: Scene) -> Optional[Dict]:
        """
        Checks if a random interactive event should trigger for a scene being shot.
        This is the main entry point for event triggering.
        """
        if not scene.bloc_id or not scene.final_cast:
            return None

        bloc_db = self.session.query(ShootingBlocDB).get(scene.bloc_id)
        if not bloc_db:
            return None

        active_policies = set(bloc_db.on_set_policies or [])
        all_production_tiers = bloc_db.production_settings or {}
        cast_talent_ids = list(scene.final_cast.values())
        if not cast_talent_ids: return None

        action_segment_tags = {seg.tag_name for seg in scene.action_segments}
        all_scene_tags = set(scene.global_tags) | set(scene.assigned_tags.keys()) | set(scene.auto_tags) | action_segment_tags
        scene_tag_concepts = set()
        for tag_name in all_scene_tags:
            tag_def = self.data_manager.tag_definitions.get(tag_name, {})
            scene_tag_concepts.add(tag_name) 
            if concept := tag_def.get('concept'):
                scene_tag_concepts.add(concept)
        
        cast_genders_db = self.session.query(TalentDB.gender).filter(TalentDB.id.in_(cast_talent_ids)).distinct().all()
        cast_genders = {g[0] for g in cast_genders_db}
        cast_size = len(cast_talent_ids)
        
        event_to_trigger = None
        triggering_talent_id = None

        if bloc_db.production_settings:
            base_bad_chance = self.data_manager.game_config.get("base_bad_event_chance_per_category", 0.10)
            base_good_chance = self.data_manager.game_config.get("base_good_event_chance_per_category", 0.08)
            
            categories = list(bloc_db.production_settings.keys())
            random.shuffle(categories)
            
            for category in categories:
                tier_name = bloc_db.production_settings[category]
                tier_data = next((t for t in self.data_manager.production_settings_data.get(category, []) if t['tier_name'] == tier_name), None)
                if not tier_data: continue

                bad_mod = tier_data.get('bad_event_chance_modifier', 1.0)
                if random.random() < (base_bad_chance * bad_mod):
                    result = self._select_triggering_talent_weighted(cast_talent_ids, 'bad')
                    if result:
                        selected_id, selected_pro = result
                        context = { 'scene': scene, 'tier_name': tier_name, 'all_production_tiers': all_production_tiers, 'active_policies': active_policies, 'cast_genders': cast_genders, 'cast_size': cast_size, 'scene_tag_concepts': scene_tag_concepts, 'triggering_talent_id': selected_id, 'triggering_talent_pro': selected_pro }
                        event_to_trigger = self._select_event_from_pool(category, 'bad', context)
                        if event_to_trigger: triggering_talent_id = selected_id; break
                
                good_mod = tier_data.get('good_event_chance_modifier', 1.0)
                if random.random() < (base_good_chance * good_mod):
                    result = self._select_triggering_talent_weighted(cast_talent_ids, 'good')
                    if result:
                        selected_id, selected_pro = result
                        context = { 'scene': scene, 'tier_name': tier_name, 'all_production_tiers': all_production_tiers, 'active_policies': active_policies, 'cast_genders': cast_genders, 'cast_size': cast_size, 'scene_tag_concepts': scene_tag_concepts, 'triggering_talent_id': selected_id, 'triggering_talent_pro': selected_pro }
                        event_to_trigger = self._select_event_from_pool(category, 'good', context)
                        if event_to_trigger: triggering_talent_id = selected_id; break
            
            if event_to_trigger:
                return { 'event_data': event_to_trigger, 'scene_id': scene.id, 'talent_id': triggering_talent_id }

        base_policy_chance = self.data_manager.game_config.get("base_policy_event_chance", 0.15)
        if random.random() < base_policy_chance:
            result = self._select_triggering_talent_weighted(cast_talent_ids, 'bad')
            if result:
                selected_id, selected_pro = result
                context = { 'scene': scene, 'all_production_tiers': all_production_tiers, 'active_policies': active_policies, 'cast_genders': cast_genders, 'cast_size': cast_size, 'scene_tag_concepts': scene_tag_concepts, 'triggering_talent_id': selected_id, 'triggering_talent_pro': selected_pro}
                event_to_trigger = self._select_event_from_pool('Policy', 'bad', context)
                if event_to_trigger:
                    return { 'event_data': event_to_trigger, 'scene_id': scene.id, 'talent_id': selected_id }
        
        return None

    def _check_event_conditions(self, conditions: List[Dict], context: Dict) -> bool:
        if not conditions: return True

        scene = context.get('scene')
        triggering_talent_id = context.get('triggering_talent_id')
        triggering_talent_pro = context.get('triggering_talent_pro')
        active_policies, cast_genders, cast_size = context.get('active_policies', set()), context.get('cast_genders', set()), context.get('cast_size', 0)
        scene_tag_concepts, all_production_tiers = context.get('scene_tag_concepts', set()), context.get('all_production_tiers', {})

        for req in conditions:
            req_type = req.get('type')
            if req_type == 'policy_active' and req.get('id') not in active_policies: return False
            elif req_type == 'policy_inactive' and req.get('id') in active_policies: return False
            elif req_type == 'cast_has_gender' and req.get('gender') not in cast_genders: return False
            elif req_type == 'talent_professionalism_above' and (triggering_talent_pro is None or triggering_talent_pro <= req.get('value', 10)): return False
            elif req_type == 'talent_professionalism_below' and (triggering_talent_pro is None or triggering_talent_pro >= req.get('value', 0)): return False
            elif req_type == 'talent_participates_in_concept':
                required_concept = req.get('concept')
                if not scene or not triggering_talent_id or not required_concept: return False
                talent_is_in_concept = False
                for segment in scene.get_expanded_action_segments(self.data_manager.tag_definitions):
                    if self.data_manager.tag_definitions.get(segment.tag_name, {}).get('concept') == required_concept:
                        for assignment in segment.slot_assignments:
                            if scene.final_cast.get(str(assignment.virtual_performer_id)) == triggering_talent_id:
                                talent_is_in_concept = True; break
                    if talent_is_in_concept: break
                if not talent_is_in_concept: return False
            elif req_type == 'scene_has_tag_concept' and req.get('concept') not in scene_tag_concepts: return False
            elif req_type == 'has_production_tier' and all_production_tiers.get(req.get('category')) != req.get('tier_name'): return False
            elif req_type == 'cast_size_is':
                comparison, value = req.get('comparison'), req.get('value')
                if comparison == 'gte' and not cast_size >= value: return False
                elif comparison == 'lte' and not cast_size <= value: return False
                elif comparison == 'eq' and not cast_size == value: return False
                elif comparison == 'gt' and not cast_size > value: return False
                elif comparison == 'lt' and not cast_size < value: return False
            else: return False
        return True

    def _select_event_from_pool(self, category: str, event_type: str, context: Dict) -> Optional[Dict]:
        possible_events, tier_name = [], context.get('tier_name')
        for event in self.data_manager.scene_events.values():
            if event.get('category') == category and event.get('type') == event_type:
                if (tiers := event.get('triggering_tiers')) and tier_name not in tiers: continue
                if not self._check_event_conditions(event.get('triggering_conditions'), context): continue
                possible_events.append(event)
        if not possible_events: return None
        weights = [e.get('base_chance', 1.0) for e in possible_events]
        return random.choices(possible_events, weights=weights, k=1)[0]
    
    def _select_triggering_talent_weighted(self, cast_talent_ids: List[int], event_type: str) -> Optional[Tuple[int, int]]:
        if not cast_talent_ids: return None
        cast_pro_scores_db = self.session.query(TalentDB.id, TalentDB.professionalism).filter(TalentDB.id.in_(cast_talent_ids)).all()
        if not cast_pro_scores_db: return None
        talent_pro_map = {row.id: row.professionalism for row in cast_pro_scores_db}
        talent_ids, professionalism_scores = list(talent_pro_map.keys()), list(talent_pro_map.values())
        if event_type == 'bad':
            max_pro = self.data_manager.game_config.get("max_attribute_level", 10)
            weights = [(max_pro + 1) - score for score in professionalism_scores]
        elif event_type == 'good':
            weights = [score + 1 for score in professionalism_scores]
        else:
            selected_id = random.choice(talent_ids)
            return (selected_id, talent_pro_map[selected_id])
        if sum(weights) == 0:
            selected_id = random.choice(talent_ids)
            return (selected_id, talent_pro_map[selected_id])
        selected_id = random.choices(talent_ids, weights=weights, k=1)[0]
        return (selected_id, talent_pro_map[selected_id])

    # --- Methods Moved from GameController (Event Resolution) ---

    def resolve_interactive_event(self, event_id: str, scene_id: int, talent_id: int, choice_id: str) -> Dict:
        """
        Applies effects of a player's choice and returns the outcome for the controller to handle.
        Outcome includes shoot modifiers, cancellation status, and if a new event was chained.
        """
        outcome = {
            "modifiers": defaultdict(lambda: defaultdict(dict)),
            "scene_was_cancelled": False,
            "chained_event_triggered": False
        }
        event_data = self.data_manager.scene_events.get(event_id)
        if not event_data:
            logger.error(f"[ERROR] Could not find event data for id: {event_id}")
            return outcome

        choice_data = next((c for c in event_data.get('choices', []) if c.get('id') == choice_id), None)
        if not choice_data:
            logger.error(f"[ERROR] Could not find choice data for id: {choice_id} in event {event_id}")
            return outcome
        
        talent = self.talent_service.get_talent_by_id(talent_id)
        scene_db = self.session.query(SceneDB).options(joinedload(SceneDB.cast)).get(scene_id)
        
        # Resolve special targets first
        other_talent_name = None
        other_talent_id = None
        effects = choice_data.get('effects', []) or []
        if any(eff.get('target') == 'other_talent_in_scene' for eff in effects) and scene_db:
            cast_ids = [c.talent_id for c in scene_db.cast if c.talent_id != talent_id]
            if cast_ids:
                other_talent_id = random.choice(cast_ids)
                other_talent_db = self.session.query(TalentDB.alias).filter_by(id=other_talent_id).one_or_none()
                if other_talent_db: other_talent_name = other_talent_db.alias
        
        # The recursive helper to process effects and their nested outcomes
        def apply_effects(effects_list: List[Dict], current_outcome: Dict):
            for effect in effects_list:
                effect_type = effect.get('type')
                if effect_type == 'add_cost':
                    cost = effect.get('amount', 0)
                    if self.game_state.money >= cost:
                        money_info = self.session.query(GameInfoDB).filter_by(key='money').one()
                        self.game_state.money -= cost
                        money_info.value = str(self.game_state.money)
                        self.signals.money_changed.emit(self.game_state.money)
                elif effect_type == 'notification':
                    message = effect.get('message', '...').replace('{talent_name}', talent.alias if talent else 'N/A')
                    if other_talent_name: message = message.replace('{other_talent_name}', other_talent_name)
                    if scene_db: message = message.replace('{scene_title}', scene_db.title)
                    self.signals.notification_posted.emit(message)
                elif effect_type == 'cancel_scene':
                    if not scene_db: continue
                    total_salary_cost = sum(c.salary for c in scene_db.cast)
                    money_info = self.session.query(GameInfoDB).filter_by(key='money').one()
                    self.game_state.money -= total_salary_cost
                    money_info.value = str(self.game_state.money)
                    self.signals.money_changed.emit(self.game_state.money)
                    
                    # Instead of calling a service, modify the outcome dictionary
                    current_outcome["scene_was_cancelled"] = True
                    reason = effect.get('reason', 'Event')
                    # We still post the notification here, as this service has the context
                    self.signals.notification_posted.emit(f"Scene '{scene_db.title}' cancelled ({reason}). Lost salary costs of ${total_salary_cost:,}.")
                elif effect_type == 'cancel_scene':
                    if not scene_db or not self.scene_service: continue
                    total_salary_cost = sum(c.salary for c in scene_db.cast)
                    money_info = self.session.query(GameInfoDB).filter_by(key='money').one()
                    self.game_state.money -= total_salary_cost
                    money_info.value = str(self.game_state.money)
                    self.signals.money_changed.emit(self.game_state.money)
                    # Use the service to delete, but don't commit here. Controller handles commit.
                    deleted_title = self.scene_service.delete_scene(scene_id, penalty_percentage=0.0)
                    if deleted_title:
                        current_outcome["scene_was_cancelled"] = True
                        reason = effect.get('reason', 'Event')
                        self.signals.notification_posted.emit(f"Scene '{deleted_title}' cancelled ({reason}). Lost salary costs of ${total_salary_cost:,}.")
                elif effect_type in ('modify_performer_contribution', 'modify_performer_contribution_random'):
                    target_id = talent_id if effect.get('target') == 'triggering_talent' else other_talent_id
                    if target_id:
                        reason = effect.get('reason', 'Event')
                        mod_data = {'min_mod': effect.get('min_mod'), 'max_mod': effect.get('max_mod')} if effect_type.endswith('random') else {'modifier': effect.get('modifier')}
                        mod_data['reason'] = reason
                        current_outcome['modifiers']['performer_mods'][target_id] = mod_data
                elif effect_type == 'modify_scene_quality':
                    current_outcome['modifiers']['quality_mods']['overall'] = {'modifier': effect.get('modifier', 1.0), 'reason': effect.get('reason', 'Event')}
                elif effect_type == 'trigger_event':
                    new_event_id = effect.get('event_id')
                    if new_event_data := self.data_manager.scene_events.get(new_event_id):
                        self.signals.interactive_event_triggered.emit(new_event_data, scene_id, talent_id)
                        current_outcome["chained_event_triggered"] = True
                        return # Stop processing, a new event takes over
                    else:
                        logger.error(f"[ERROR] Chained event error: Could not find event with id '{new_event_id}'")
                elif effect_type == 'random_outcome':
                    outcomes = effect.get('outcomes', [])
                    if outcomes:
                        weights = [o.get('chance', 1.0) for o in outcomes]
                        chosen_outcome = random.choices(outcomes, weights=weights, k=1)[0]
                        apply_effects(chosen_outcome.get('effects', []), current_outcome)
                        if current_outcome["chained_event_triggered"]: return
            
        apply_effects(effects, outcome)
        return outcome