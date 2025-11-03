from typing import Dict

from data.game_state import Talent
from services.models.configs import SceneCalculationConfig

class TalentAffinityCalculator:
    """A pure calculation service for talent-related logic."""

    def __init__(self, config: SceneCalculationConfig):
        self.config = config

    def recalculate_talent_age_affinities(self, talent: Talent) -> Dict:
        """Recalculates affinities affected by age."""
        new_affinities = talent.tag_affinities.copy()
        rules = self.config.age_based_affinity_rules
        
        if not rules:
            return new_affinities
            
        for rule in rules:
            tag_name = rule.get('tag')
            if talent.age >= rule.get('min_age') and talent.age <= rule.get('max_age'):
                new_affinities[tag_name] = rule.get('affinity_score', 0)
        return new_affinities