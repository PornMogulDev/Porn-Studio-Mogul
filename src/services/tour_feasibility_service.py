import logging
from typing import Optional, Dict, List

from data.data_manager import DataManager
from services.models.configs import HiringConfig
from database.db_models import TalentDB, SceneDB

logger = logging.getLogger(__name__)

class TourFeasibilityService:
    """
    A pure logic class to check if a talent can go on a tour and determine
    their accommodation requirements based on business rules.
    """
    def __init__(self, data_manager: DataManager, config: HiringConfig):
        self.data_manager = data_manager
        self.config = config

    def check_schedule_conflict(self, start_week: int, start_year: int, duration_weeks: int,
                                bookings_by_week: Dict[int, List[SceneDB]]) -> Optional[str]:
        """Checks if any week within the proposed tour duration has an existing booking."""
        current_week, current_year = start_week, start_year
        for _ in range(duration_weeks):
            if bookings_by_week.get(current_week):
                return f"Has an existing booking in Week {current_week}, {current_year}."
            
            # Advance to the next week, handling year wrap-around
            current_week += 1
            if current_week > 52:
                current_week = 1
                current_year += 1
        return None

    def determine_accommodation_tier(self, talent: TalentDB) -> Optional[str]:
        """
        Determines the required accommodation tier for a talent.
        - A talent DEMANDS the single most expensive tier whose requirements they meet.
        - If they don't demand any tier, they are assigned the cheapest available tier.
        """
        pop_scalar = self.config.pickiness_popularity_scalar
        amb_scalar = self.config.pickiness_ambition_scalar
        total_popularity = sum(p.score for p in talent.popularity_scores) if talent.popularity_scores else 0
        pickiness_score = (total_popularity * pop_scalar) + (talent.ambition * amb_scalar)

        # Tiers are pre-sorted by cost (cheapest to most expensive) in DataManager
        available_tiers = list(self.data_manager.accommodation_tiers.values())
        if not available_tiers:
            return None # No accommodation configured in game data

        # 1. Iterate from most expensive to cheapest to find what they demand.
        #    The first match is the highest tier they qualify for, which is their demand.
        for tier in reversed(available_tiers):
            if pickiness_score >= tier['pickiness_requirement']:
                return tier['id']

        # 2. If the loop completes, their pickiness is too low to demand even the
        #    cheapest tier. In this case, they are assigned the absolute cheapest tier.
        return available_tiers[0]['id']