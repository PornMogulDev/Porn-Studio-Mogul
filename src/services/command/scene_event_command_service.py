import logging
import random
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import joinedload, selectinload, Session

from data.data_manager import DataManager
from services.query.game_query_service import GameQueryService
from database.db_models import TalentDB, ShootingBlocDB, GameInfoDB, SceneDB
from services.models.results import EventResolutionResult, EventAction

logger = logging.getLogger(__name__)


class SceneEventCommandService:
    """
    Handles the resolution of interactive events that occur during scene shoots.
    This service is self-contained and manages its own database transactions.
    It returns a result DTO to the controller, which then orchestrates the next step.
    """
    def __init__(self, session_factory, data_manager: DataManager, query_service: GameQueryService):
        self.session_factory = session_factory
        self.data_manager = data_manager
        self.query_service = query_service

    def _calculate_proportional_cost(self, session: Session, scene_db: SceneDB, multiplier: float) -> int:
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

    def resolve_interactive_event(self, event_id: str, scene_id: int, talent_id: int, choice_id: str) -> EventResolutionResult:
        """
        Applies effects of a player's choice, handling its own transaction.
        Returns an EventResolutionResult DTO detailing the outcome.
        """
        session = self.session_factory()
        modifiers = defaultdict(lambda: defaultdict(dict))
        try:
            event_data = self.data_manager.scene_events.get(event_id)
            if not event_data:
                logger.error(f"Could not find event data for id: {event_id}")
                return EventResolutionResult(next_action=EventAction.CONTINUE_SHOOT) # Fail safe

            choice_data = next((c for c in event_data.get('choices', []) if c.get('id') == choice_id), None)
            if not choice_data:
                logger.error(f"Could not find choice data for id: {choice_id} in event {event_id}")
                return EventResolutionResult(next_action=EventAction.CONTINUE_SHOOT) # Fail safe
            
            talent = self.query_service.get_talent_by_id(talent_id)
            scene_db = session.query(SceneDB).options(joinedload(SceneDB.cast)).get(scene_id)
            
            other_talent_name = None
            other_talent_id = None
            effects = choice_data.get('effects', []) or []
            if any(eff.get('target') == 'other_talent_in_scene' for eff in effects) and scene_db:
                cast_ids = [c.talent_id for c in scene_db.cast if c.talent_id != talent_id]
                if cast_ids:
                    other_talent_id = random.choice(cast_ids)
                    other_talent_db = session.query(TalentDB.alias).filter_by(id=other_talent_id).one_or_none()
                    if other_talent_db: other_talent_name = other_talent_db.alias
            
            def apply_effects(effects_list: List[Dict]) -> EventResolutionResult:
                notification_parts = []
                for effect in effects_list:
                    effect_type = effect.get('type')
                    if effect_type == 'add_cost':
                        cost = 0
                        if effect.get('cost_type') == 'proportional':
                            cost = self._calculate_proportional_cost(session, scene_db, effect.get('amount', 0.0))
                        else: cost = effect.get('amount', 0)
                        if cost > 0:
                            money_info = session.query(GameInfoDB).filter_by(key='money').one()
                            money_info.value = str(int(float(money_info.value)) - cost)
                    elif effect_type == 'notification':
                        message = effect.get('message', '...').replace('{talent_name}', talent.alias if talent else 'N/A')
                        if other_talent_name: message = message.replace('{other_talent_name}', other_talent_name)
                        if scene_db: message = message.replace('{scene_title}', scene_db.title)
                        notification_parts.append(message)
                    elif effect_type == 'cancel_scene':
                        if not scene_db: continue
                        cost_multiplier = effect.get('cost_multiplier', 1.0)
                        reason = effect.get('reason', 'Event')
                        notification = f"Scene '{scene_db.title}' cancelled ({reason})."
                        # DO NOT delete the scene here. Return an action to the controller.
                        return EventResolutionResult(next_action=EventAction.CANCEL_SCENE, cancellation_penalty=cost_multiplier, notification=notification)
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
                            # DO NOT emit a signal here. Return an action to the controller.
                            payload = {'event_data': new_event_data, 'scene_id': scene_id, 'talent_id': talent_id}
                            return EventResolutionResult(next_action=EventAction.CHAIN_EVENT, chained_event_payload=payload)
                        else:
                            logger.error(f"Chained event error: Could not find event with id '{new_event_id}'")
                    elif effect_type == 'random_outcome':
                        outcomes = effect.get('outcomes', [])
                        if outcomes:
                            weights = [o.get('chance', 1.0) for o in outcomes]
                            chosen_outcome = random.choices(outcomes, weights=weights, k=1)[0]
                            return apply_effects(chosen_outcome.get('effects', []))
                
                final_notification = " ".join(notification_parts) if notification_parts else None
                return EventResolutionResult(next_action=EventAction.CONTINUE_SHOOT, shoot_modifiers=modifiers, notification=final_notification)

            result = apply_effects(effects)
            
            # Commit only if the action doesn't require further orchestration (like chaining)
            if result.next_action != EventAction.CHAIN_EVENT:
                session.commit()
            return result
        except Exception as e:
            logger.error(f"Error resolving event {event_id}: {e}", exc_info=True)
            session.rollback()
            return EventResolutionResult(next_action=EventAction.CONTINUE_SHOOT) # Fail safe
        finally:
            session.close()