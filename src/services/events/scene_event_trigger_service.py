import logging
import random
from typing import Dict, List, Optional
from sqlalchemy.orm import selectinload, Session

from data.game_state import Scene, Talent
from data.data_manager import DataManager
from database.db_models import TalentDB, ShootingBlocDB
from services.events.event_conditions import (
    PolicyActiveCondition, PolicyInactiveCondition, CastHasGenderCondition,
    SceneHasTagConceptCondition, CastSizeIsCondition,
    TalentProfessionalismAboveCondition, TalentProfessionalismBelowCondition,
    TalentPhysicalAttributeCondition, TalentParticipatesInConceptCondition,
    HasProductionTierCondition, NotHasProductionTierCondition
)

logger = logging.getLogger(__name__)


class SceneEventTriggerService:
    """
    Checks if a random interactive event should trigger for a scene being shot.
    This is a read-only style service that makes a determination based on game state.
    """
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager
        
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
                        context = self._build_context(scene, all_production_tiers, active_policies, cast_genders, cast_size, scene_tag_concepts, triggering_talent, tier_name)
                        event_to_trigger = self._select_event_from_pool(category, 'bad', context)
                        if event_to_trigger:
                            break
                
                good_mod = tier_data.get('good_event_chance_modifier', 1.0)
                if random.random() < (base_good_chance * good_mod):
                    triggering_talent = self._select_triggering_talent_weighted(cast_talents_db, 'good')
                    if triggering_talent:
                        context = self._build_context(scene, all_production_tiers, active_policies, cast_genders, cast_size, scene_tag_concepts, triggering_talent, tier_name)
                        event_to_trigger = self._select_event_from_pool(category, 'good', context)
                        if event_to_trigger:
                            break
                if event_to_trigger: break
            
            if event_to_trigger and triggering_talent:
                return { 'event_data': event_to_trigger, 'scene_id': scene.id, 'talent_id': triggering_talent.id }

        base_policy_chance = self.data_manager.game_config.get("base_policy_event_chance", 0.15)
        if random.random() < base_policy_chance:
            triggering_talent = self._select_triggering_talent_weighted(cast_talents_db, 'bad')
            if triggering_talent:
                context = self._build_context(scene, all_production_tiers, active_policies, cast_genders, cast_size, scene_tag_concepts, triggering_talent)
                event_to_trigger = self._select_event_from_pool('Policy', 'bad', context)
                if event_to_trigger:
                    return { 'event_data': event_to_trigger, 'scene_id': scene.id, 'talent_id': triggering_talent.id }
        
        return None

    def _build_context(self, scene: Scene, all_production_tiers: Dict, active_policies: set, cast_genders: set, cast_size: int, scene_tag_concepts: set, triggering_talent: TalentDB, tier_name: Optional[str] = None) -> Dict:
        """Helper to construct the context dictionary for condition checking."""
        return {
            'scene': scene, 'tier_name': tier_name,
            'all_production_tiers': all_production_tiers,
            'active_policies': active_policies, 'cast_genders': cast_genders,
            'cast_size': cast_size, 'scene_tag_concepts': scene_tag_concepts,
            'triggering_talent': triggering_talent,
            'triggering_talent_id': triggering_talent.id,
            'triggering_talent_pro': triggering_talent.professionalism,
            'data_manager': self.data_manager
        }

    def _check_event_conditions(self, conditions: List[Dict], context: Dict) -> bool:
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
    
    def _select_triggering_talent_weighted(self, cast_talents_db: List[TalentDB], event_type: str) -> Optional[TalentDB]:
        if not cast_talents_db: return None
        talent_ids = [t.id for t in cast_talents_db]
        professionalism_scores = [t.professionalism for t in cast_talents_db]
        if event_type == 'bad':
            max_pro = self.data_manager.game_config.get("max_attribute_level", 10)
            weights = [(max_pro + 1) - score for score in professionalism_scores]
        elif event_type == 'good':
            weights = [score + 1 for score in professionalism_scores]
        else:
            return random.choice(cast_talents_db)
        
        if sum(weights) == 0:
            return random.choice(cast_talents_db)
        else:
            selected_id = random.choices(talent_ids, weights=weights, k=1)[0]
            return next((t for t in cast_talents_db if t.id == selected_id), None)