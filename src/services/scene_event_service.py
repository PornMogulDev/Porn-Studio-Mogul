import logging
import random
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from sqlalchemy.orm import joinedload, selectinload

from data.game_state import Scene, Talent
from data.data_manager import DataManager
from services.talent_service import TalentService
from core.interfaces import GameSignals
from database.db_models import TalentDB, ShootingBlocDB, GameInfoDB, SceneDB

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
                    triggering_talent = self._select_triggering_talent_weighted(cast_talent_ids, 'bad')
                    if triggering_talent:
                        context = {
                            'scene': scene, 'tier_name': tier_name,
                            'all_production_tiers': all_production_tiers,
                            'active_policies': active_policies, 'cast_genders': cast_genders,
                            'cast_size': cast_size, 'scene_tag_concepts': scene_tag_concepts,
                            'triggering_talent': triggering_talent,
                            'triggering_talent_id': triggering_talent.id,
                            'triggering_talent_pro': triggering_talent.professionalism
                        }
                        event_to_trigger = self._select_event_from_pool(category, 'bad', context)
                        
                        if event_to_trigger:
                            triggering_talent_id = triggering_talent.id
                            break
                
                good_mod = tier_data.get('good_event_chance_modifier', 1.0)
                if random.random() < (base_good_chance * good_mod):
                    triggering_talent = self._select_triggering_talent_weighted(cast_talent_ids, 'good')
                    if triggering_talent:
                        context = { 'scene': scene, 'tier_name': tier_name, 'all_production_tiers': all_production_tiers, 'active_policies': active_policies, 'cast_genders': cast_genders, 'cast_size': cast_size, 'scene_tag_concepts': scene_tag_concepts, 'triggering_talent': triggering_talent, 'triggering_talent_id': triggering_talent.id, 'triggering_talent_pro': triggering_talent.professionalism }
                        event_to_trigger = self._select_event_from_pool(category, 'good', context)
                        if event_to_trigger: triggering_talent_id = triggering_talent.id; break
            
            if event_to_trigger:
                return { 'event_data': event_to_trigger, 'scene_id': scene.id, 'talent_id': triggering_talent.id }

        base_policy_chance = self.data_manager.game_config.get("base_policy_event_chance", 0.15)
        if random.random() < base_policy_chance:
            triggering_talent = self._select_triggering_talent_weighted(cast_talent_ids, 'bad')
            if triggering_talent:
                context = { 'scene': scene, 'all_production_tiers': all_production_tiers, 'active_policies': active_policies, 'cast_genders': cast_genders, 'cast_size': cast_size, 'scene_tag_concepts': scene_tag_concepts, 'triggering_talent': triggering_talent, 'triggering_talent_id': triggering_talent.id, 'triggering_talent_pro': triggering_talent.professionalism}
                event_to_trigger = self._select_event_from_pool('Policy', 'bad', context)
                if event_to_trigger:
                    return { 'event_data': event_to_trigger, 'scene_id': scene.id, 'talent_id': triggering_talent.id }
        
        return None

    def _check_event_conditions(self, conditions: List[Dict], context: Dict) -> bool:
        if not conditions: return True

        scene = context.get('scene')
        triggering_talent = context.get('triggering_talent')
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
                required_roles = req.get('roles')
                if not scene or not triggering_talent_id or not required_concept: return False
                talent_is_in_concept = False
                for segment in scene.get_expanded_action_segments(self.data_manager.tag_definitions):
                    tag_def = self.data_manager.tag_definitions.get(segment.tag_name, {})
                    if tag_def.get('concept') == required_concept:
                        for assignment in segment.slot_assignments:
                            if scene.final_cast.get(str(assignment.virtual_performer_id)) == triggering_talent_id:
                                # Talent found in the concept. Now check role if required.
                                if not required_roles:
                                    talent_is_in_concept = True
                                    break
                                
                                try:
                                    _, role, _ = assignment.slot_id.rsplit('_', 2)
                                    if role in required_roles:
                                        talent_is_in_concept = True
                                        break
                                except ValueError:
                                    continue
                    if talent_is_in_concept: break
                if not talent_is_in_concept: return False
            elif req_type == 'talent_physical_attribute':
                if not triggering_talent: return False
                key, comparison, value = req.get('key'), req.get('comparison'), req.get('value')
                actual_value = getattr(triggering_talent, key, None)
                if actual_value is None: return False
                is_met = False
                if comparison == 'gte' and actual_value >= value: is_met = True
                elif comparison == 'lte' and actual_value <= value: is_met = True
                elif comparison == 'eq' and actual_value == value: is_met = True
                if not is_met: return False
            elif req_type == 'scene_has_tag_concept' and req.get('concept') not in scene_tag_concepts: return False
            elif req_type == 'has_production_tier' and all_production_tiers.get(req.get('category')) != req.get('tier_name'): return False
            elif req_type == 'not_has_production_tier' and all_production_tiers.get(req.get('category')) == req.get('tier_name'): return False
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
    
    def _select_triggering_talent_weighted(self, cast_talent_ids: List[int], event_type: str) -> Optional[Talent]:
        cast_talents_db = self.session.query(TalentDB).filter(TalentDB.id.in_(cast_talent_ids)).all()
        if not cast_talents_db: return None

        talent_map = {t.id: t for t in cast_talents_db}
        talent_ids = list(talent_map.keys())
        professionalism_scores = [talent_map[tid].professionalism for tid in talent_ids]
        if event_type == 'bad':
            max_pro = self.data_manager.game_config.get("max_attribute_level", 10)
            weights = [(max_pro + 1) - score for score in professionalism_scores]
        elif event_type == 'good':
            weights = [score + 1 for score in professionalism_scores]
        else:
            selected_id = random.choice(talent_ids)
            return talent_map[selected_id].to_dataclass(Talent)
        if sum(weights) == 0:
            selected_id = random.choice(talent_ids)
        else:
            selected_id = random.choices(talent_ids, weights=weights, k=1)[0]

        return talent_map[selected_id].to_dataclass(Talent)

    def _calculate_proportional_cost(self, scene_db: SceneDB, multiplier: float) -> int:
        """Calculates a cost based on the scene's total one-time budget."""
        salary_cost = sum(c.salary for c in scene_db.cast)
        prod_cost_per_scene = 0
        if scene_db.bloc_id:
            bloc_db = self.session.query(ShootingBlocDB).options(selectinload(ShootingBlocDB.scenes)).get(scene_db.bloc_id)
            if bloc_db and bloc_db.scenes:
                num_scenes_in_bloc = len(bloc_db.scenes)
                if num_scenes_in_bloc > 0:
                    prod_cost_per_scene = bloc_db.production_cost / num_scenes_in_bloc
        total_scene_budget = salary_cost + prod_cost_per_scene
        return int(total_scene_budget * multiplier)

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
                    cost = 0
                    if effect.get('cost_type') == 'proportional':
                        cost = self._calculate_proportional_cost(scene_db, effect.get('amount', 0.0))
                    else:
                        cost = effect.get('amount', 0)
                    if cost > 0:
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
                    cost_multiplier = effect.get('cost_multiplier', 1.0)
                    cost_to_lose = self._calculate_proportional_cost(scene_db, cost_multiplier)
                    money_info = self.session.query(GameInfoDB).filter_by(key='money').one()
                    self.game_state.money -= cost_to_lose
                    money_info.value = str(self.game_state.money)
                    self.signals.money_changed.emit(self.game_state.money)
                    
                    current_outcome["scene_was_cancelled"] = True
                    reason = effect.get('reason', 'Event')
                    self.signals.notification_posted.emit(f"Scene '{scene_db.title}' cancelled ({reason}). Lost costs of ${cost_to_lose:,}.")
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