import logging
import random
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from sqlalchemy.orm import joinedload, selectinload, Session

from data.game_state import Scene, Talent
from data.data_manager import DataManager
from services.query.game_query_service import GameQueryService
from core.game_signals import GameSignals
from database.db_models import TalentDB, TalentChemistryDB, ShootingBlocDB, GameInfoDB, SceneDB
from services.events.event_conditions import (
    PolicyActiveCondition, PolicyInactiveCondition, CastHasGenderCondition,
    SceneHasTagConceptCondition, CastSizeIsCondition,
    TalentProfessionalismAboveCondition, TalentProfessionalismBelowCondition,
    TalentPhysicalAttributeCondition, TalentParticipatesInConceptCondition,
    HasProductionTierCondition, NotHasProductionTierCondition
)


if TYPE_CHECKING:
    from services.command.scene_command_service import SceneCommandService

logger = logging.getLogger(__name__)


class SceneEventService:
    """
    Handles the triggering and resolution of interactive events that occur during scene shoots.
    This service is self-contained and manages its own database transactions for event resolution.
    """
    def __init__(self, session_factory, signals: GameSignals, data_manager: DataManager,
                 query_service: GameQueryService, scene_command_service: 'SceneCommandService'):
        self.session_factory = session_factory
        self.signals = signals
        self.data_manager = data_manager
        self.query_service = query_service
        self.scene_command_service = scene_command_service
        
        # Condition Factory: Maps condition types from JSON to handler classes
        self._condition_handlers = {
            'policy_active': PolicyActiveCondition(),
            'policy_inactive': PolicyInactiveCondition(),
            'cast_has_gender': CastHasGenderCondition(),
            'scene_has_tag_concept': SceneHasTagConceptCondition(),
            'cast_size_is': CastSizeIsCondition(),
            'talent_professionalism_above': TalentProfessionalismAboveCondition(),
            'talent_professionalism_below': TalentProfessionalismBelowCondition(),
            'talent_physical_attribute': TalentPhysicalAttributeCondition(),
            'talent_participates_in_concept': TalentParticipatesInConceptCondition(),
            'has_production_tier': HasProductionTierCondition(),
            'not_has_production_tier': NotHasProductionTierCondition(),
        }

    def check_for_shoot_event(self, session: Session, scene: Scene) -> Optional[Dict]:
        """
        Checks if a random interactive event should trigger for a scene being shot.
        This is the main entry point for event triggering.
        """
        if not scene.bloc_id or not scene.final_cast:
            return None

        bloc_db = session.query(ShootingBlocDB).get(scene.bloc_id)
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
        
        cast_genders_db = session.query(TalentDB.gender).filter(TalentDB.id.in_(cast_talent_ids)).distinct().all()
        cast_genders = {g[0] for g in cast_genders_db}
        cast_size = len(cast_talent_ids)
        
        # Pre-fetch all cast TalentDB objects to avoid querying in a loop
        cast_talents_db = session.query(TalentDB).options(
            selectinload(TalentDB.popularity_scores),
            selectinload(TalentDB.chemistry_a),
            selectinload(TalentDB.chemistry_b)
        ).filter(TalentDB.id.in_(cast_talent_ids)).all()
        
        event_to_trigger = None
        triggering_talent_id = None
        triggering_talent = None

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
                    triggering_talent = self._select_triggering_talent_weighted(cast_talents_db, 'bad')
                    if triggering_talent:
                        context = {
                            'scene': scene, 'tier_name': tier_name,
                            'all_production_tiers': all_production_tiers,
                            'active_policies': active_policies, 'cast_genders': cast_genders,
                            'cast_size': cast_size, 'scene_tag_concepts': scene_tag_concepts,
                            'triggering_talent': triggering_talent,
                            'triggering_talent_id': triggering_talent.id,
                            'triggering_talent_pro': triggering_talent.professionalism,
                            'data_manager': self.data_manager
                        }
                        event_to_trigger = self._select_event_from_pool(category, 'bad', context)
                        
                        if event_to_trigger:
                            triggering_talent_id = triggering_talent.id
                            break
                
                good_mod = tier_data.get('good_event_chance_modifier', 1.0)
                if random.random() < (base_good_chance * good_mod):
                    triggering_talent = self._select_triggering_talent_weighted(cast_talents_db, 'good')
                    if triggering_talent:
                        context = {
                            'scene': scene, 'tier_name': tier_name,
                            'all_production_tiers': all_production_tiers,
                            'active_policies': active_policies, 'cast_genders': cast_genders,
                            'cast_size': cast_size, 'scene_tag_concepts': scene_tag_concepts,
                            'triggering_talent': triggering_talent,
                            'triggering_talent_id': triggering_talent.id,
                            'triggering_talent_pro': triggering_talent.professionalism,
                            'data_manager': self.data_manager
                        }
                        event_to_trigger = self._select_event_from_pool(category, 'good', context)
                        if event_to_trigger:
                            triggering_talent_id = triggering_talent.id
                            break
            
            if event_to_trigger and triggering_talent:
                return { 'event_data': event_to_trigger, 'scene_id': scene.id, 'talent_id': triggering_talent.id }

        base_policy_chance = self.data_manager.game_config.get("base_policy_event_chance", 0.15)
        if random.random() < base_policy_chance:
            triggering_talent = self._select_triggering_talent_weighted(cast_talents_db, 'bad')
            if triggering_talent:
                context = {
                    'scene': scene, 'all_production_tiers': all_production_tiers,
                    'active_policies': active_policies, 'cast_genders': cast_genders,
                    'cast_size': cast_size, 'scene_tag_concepts': scene_tag_concepts,
                    'triggering_talent': triggering_talent,
                    'triggering_talent_id': triggering_talent.id,
                    'triggering_talent_pro': triggering_talent.professionalism,
                    'data_manager': self.data_manager
                }
                event_to_trigger = self._select_event_from_pool('Policy', 'bad', context)
                if event_to_trigger:
                    return { 'event_data': event_to_trigger, 'scene_id': scene.id, 'talent_id': triggering_talent.id }
        
        return None

    def _check_event_conditions(self, conditions: List[Dict], context: Dict) -> bool:
        """
        Validates a list of conditions using the Strategy pattern via the condition factory.
        """
        if not conditions: return True

        for req in conditions:
            handler = self._condition_handlers.get(req.get('type'))
            if not handler:
                logger.warning(f"No handler found for event condition type: {req.get('type')}")
                return False
            if not handler.check(req, context):
                return False
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
    
    def _select_triggering_talent_weighted(self, cast_talents_db: List[TalentDB], event_type: str) -> Optional[Talent]:
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

    def _calculate_proportional_cost(self, session: Session, scene_db: SceneDB, multiplier: float) -> int:
        """Calculates a cost based on the scene's total one-time budget."""
        salary_cost = sum(c.salary for c in scene_db.cast)
        prod_cost_per_scene = 0
        if scene_db.bloc_id:
            bloc_db = session.query(ShootingBlocDB).options(selectinload(ShootingBlocDB.scenes)).get(scene_db.bloc_id)
            if bloc_db and bloc_db.scenes:
                num_scenes_in_bloc = len(bloc_db.scenes)
                if num_scenes_in_bloc > 0:
                    prod_cost_per_scene = bloc_db.production_cost / num_scenes_in_bloc
        total_scene_budget = salary_cost + prod_cost_per_scene
        return int(total_scene_budget * multiplier)

    def resolve_interactive_event(self, event_id: str, scene_id: int, talent_id: int, choice_id: str) -> Tuple[bool, Dict]:
        """
        Applies effects of a player's choice, handling its own transaction.
        Returns a tuple: (was_shoot_completed, shoot_modifiers)
        """
        session = self.session_factory()
        try:
            modifiers = defaultdict(lambda: defaultdict(dict))
            event_data = self.data_manager.scene_events.get(event_id)
            if not event_data:
                logger.error(f"[ERROR] Could not find event data for id: {event_id}")
                return False, modifiers

            choice_data = next((c for c in event_data.get('choices', []) if c.get('id') == choice_id), None)
            if not choice_data:
                logger.error(f"[ERROR] Could not find choice data for id: {choice_id} in event {event_id}")
                return False, modifiers
            
            talent = self.query_service.get_talent_by_id(talent_id)
            scene_db = session.query(SceneDB).options(joinedload(SceneDB.cast)).get(scene_id)
            
            # Resolve special targets first
            other_talent_name = None
            other_talent_id = None
            effects = choice_data.get('effects', []) or []
            if any(eff.get('target') == 'other_talent_in_scene' for eff in effects) and scene_db:
                cast_ids = [c.talent_id for c in scene_db.cast if c.talent_id != talent_id]
                if cast_ids:
                    other_talent_id = random.choice(cast_ids)
                    other_talent_db = session.query(TalentDB.alias).filter_by(id=other_talent_id).one_or_none()
                    if other_talent_db: other_talent_name = other_talent_db.alias
            
            def apply_effects(session: Session, effects_list: List[Dict]) -> Tuple[bool, bool]:
                """
                Internal recursive helper to process effects.
                Returns: (is_shoot_complete, is_event_chained)
                """
                for effect in effects_list:
                    effect_type = effect.get('type')
                    if effect_type == 'add_cost':
                        cost = 0
                        if effect.get('cost_type') == 'proportional':
                            cost = self._calculate_proportional_cost(session, scene_db, effect.get('amount', 0.0))
                        else:
                            cost = effect.get('amount', 0)
                        if cost > 0:
                            money_info = session.query(GameInfoDB).filter_by(key='money').one()
                            new_money = int(float(money_info.value)) - cost
                            money_info.value = str(new_money)
                            # We don't emit money_changed here; the controller will do it after the week finishes.
                    elif effect_type == 'notification':
                        message = effect.get('message', '...').replace('{talent_name}', talent.alias if talent else 'N/A')
                        if other_talent_name: message = message.replace('{other_talent_name}', other_talent_name)
                        if scene_db: message = message.replace('{scene_title}', scene_db.title)
                        self.signals.notification_posted.emit(message)
                    elif effect_type == 'cancel_scene':
                        if not scene_db: continue
                        cost_multiplier = effect.get('cost_multiplier', 1.0)
                        # Delete the scene via the scene service. The service handles money changes.
                        # Pass silent=True because we are sending our own notification here.
                        self.scene_command_service.delete_scene(scene_id, penalty_percentage=cost_multiplier, silent=True, commit=False)
                        reason = effect.get('reason', 'Event')
                        self.signals.notification_posted.emit(f"Scene '{scene_db.title}' cancelled ({reason}).")
                        return False, False # Shoot is NOT complete, no chained event
                    elif effect_type in ('modify_performer_contribution', 'modify_performer_contribution_random'):
                        target_id = talent_id if effect.get('target') == 'triggering_talent' else other_talent_id
                        if target_id:
                            reason = effect.get('reason', 'Event')
                            mod_data = {'min_mod': effect.get('min_mod'), 'max_mod': effect.get('max_mod')} if effect_type.endswith('random') else {'modifier': effect.get('modifier')}
                            mod_data['reason'] = reason
                            modifiers['performer_mods'][target_id] = mod_data
                    elif effect_type == 'modify_scene_quality':
                        modifiers['quality_mods']['overall'] = {'modifier': effect.get('modifier', 1.0), 'reason': effect.get('reason', 'Event')}
                    elif effect_type == 'trigger_event':
                        new_event_id = effect.get('event_id')
                        if new_event_data := self.data_manager.scene_events.get(new_event_id):
                            self.signals.interactive_event_triggered.emit(new_event_data, scene_id, talent_id)
                            return False, True # Shoot is NOT complete, chained event occurred
                        else:
                            logger.error(f"[ERROR] Chained event error: Could not find event with id '{new_event_id}'")
                    elif effect_type == 'random_outcome':
                        outcomes = effect.get('outcomes', [])
                        if outcomes:
                            weights = [o.get('chance', 1.0) for o in outcomes]
                            chosen_outcome = random.choices(outcomes, weights=weights, k=1)[0]
                            is_complete, is_chained = apply_effects(chosen_outcome.get('effects', []))
                            if is_chained:
                                return False, True
                            if not is_complete:
                                return False, False
                return True, False # Shoot is complete, no chained event

            shoot_is_complete, chained_event = apply_effects(session, effects)
            if not chained_event:
                session.commit()
            return shoot_is_complete, modifiers
        except Exception as e:
            logger.error(f"Error resolving event {event_id}: {e}", exc_info=True)
            session.rollback()
            return False, modifiers
        finally:
            session.close()