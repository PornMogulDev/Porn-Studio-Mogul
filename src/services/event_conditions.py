from abc import ABC, abstractmethod
from typing import Dict, List


class ICondition(ABC):
    """
    Abstract base class for an event triggering condition.
    Each implementation represents a single, specific rule that can be checked
    against the game's context.
    """
    @abstractmethod
    def check(self, req: Dict, context: Dict) -> bool:
        """
        Checks if the condition specified in 'req' is met by the 'context'.

        Args:
            req: The dictionary defining the specific requirement
                 (e.g., {'type': 'policy_active', 'id': '...'}).
            context: The dictionary containing the current game state for the check.

        Returns:
            True if the condition is met, False otherwise.
        """
        pass


# --- Policy Conditions ---

class PolicyActiveCondition(ICondition):
    def check(self, req: Dict, context: Dict) -> bool:
        policy_id = req.get('id')
        active_policies = context.get('active_policies', set())
        return policy_id in active_policies


class PolicyInactiveCondition(ICondition):
    def check(self, req: Dict, context: Dict) -> bool:
        policy_id = req.get('id')
        active_policies = context.get('active_policies', set())
        return policy_id not in active_policies


# --- Cast & Scene Composition Conditions ---

class CastHasGenderCondition(ICondition):
    def check(self, req: Dict, context: Dict) -> bool:
        gender = req.get('gender')
        cast_genders = context.get('cast_genders', set())
        return gender in cast_genders


class SceneHasTagConceptCondition(ICondition):
    def check(self, req: Dict, context: Dict) -> bool:
        concept = req.get('concept')
        scene_tag_concepts = context.get('scene_tag_concepts', set())
        return concept in scene_tag_concepts


class CastSizeIsCondition(ICondition):
    def check(self, req: Dict, context: Dict) -> bool:
        comparison = req.get('comparison')
        value = req.get('value')
        cast_size = context.get('cast_size')

        if comparison is None or value is None or cast_size is None:
            return False

        if comparison == 'gte': return cast_size >= value
        if comparison == 'lte': return cast_size <= value
        if comparison == 'eq': return cast_size == value
        if comparison == 'gt': return cast_size > value
        if comparison == 'lt': return cast_size < value
        return False


# --- Talent-Specific Conditions ---

class TalentProfessionalismAboveCondition(ICondition):
    def check(self, req: Dict, context: Dict) -> bool:
        pro_score = context.get('triggering_talent_pro')
        value = req.get('value')
        return pro_score is not None and value is not None and pro_score > value


class TalentProfessionalismBelowCondition(ICondition):
    def check(self, req: Dict, context: Dict) -> bool:
        pro_score = context.get('triggering_talent_pro')
        value = req.get('value')
        return pro_score is not None and value is not None and pro_score < value


class TalentPhysicalAttributeCondition(ICondition):
    def check(self, req: Dict, context: Dict) -> bool:
        talent = context.get('triggering_talent')
        if not talent:
            return False

        key = req.get('key')
        comparison = req.get('comparison')
        value = req.get('value')

        if not all([key, comparison, value is not None]):
            return False

        actual_value = getattr(talent, key, None)
        if actual_value is None:
            return False

        if comparison == 'gte': return actual_value >= value
        if comparison == 'lte': return actual_value <= value
        if comparison == 'eq': return actual_value == value
        return False


class TalentParticipatesInConceptCondition(ICondition):
    def check(self, req: Dict, context: Dict) -> bool:
        scene = context.get('scene')
        talent_id = context.get('triggering_talent_id')
        data_manager = context.get('data_manager')
        required_concept = req.get('concept')
        required_roles = req.get('roles')

        if not all([scene, talent_id, data_manager, required_concept]):
            return False

        for segment in scene.get_expanded_action_segments(data_manager.tag_definitions):
            tag_def = data_manager.tag_definitions.get(segment.tag_name, {})
            if tag_def.get('concept') == required_concept:
                for assignment in segment.slot_assignments:
                    # Check if the talent is in this assignment
                    if scene.final_cast.get(str(assignment.virtual_performer_id)) == talent_id:
                        # If roles aren't specified, just finding the talent is enough
                        if not required_roles:
                            return True
                        # If roles are specified, check if the talent's role matches
                        try:
                            _, role, _ = assignment.slot_id.rsplit('_', 2)
                            if role in required_roles:
                                return True
                        except ValueError:
                            continue
        return False


# --- Production Conditions ---

class HasProductionTierCondition(ICondition):
    def check(self, req: Dict, context: Dict) -> bool:
        category = req.get('category')
        tier_name = req.get('tier_name')
        production_tiers = context.get('all_production_tiers', {})
        return production_tiers.get(category) == tier_name


class NotHasProductionTierCondition(ICondition):
    def check(self, req: Dict, context: Dict) -> bool:
        category = req.get('category')
        tier_name = req.get('tier_name')
        production_tiers = context.get('all_production_tiers', {})
        return production_tiers.get(category) != tier_name