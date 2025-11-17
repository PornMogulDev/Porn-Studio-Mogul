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
        """Determines the required or acceptable accommodation tier for a talent based on their pickiness."""
        pop_scalar = self.config.pickiness_popularity_scalar
        amb_scalar = self.config.pickiness_ambition_scalar
        total_popularity = sum(p.score for p in talent.popularity_scores) if talent.popularity_scores else 0
        pickiness_score = (total_popularity * pop_scalar) + (talent.ambition * amb_scalar)

        # Tiers are pre-sorted by cost in DataManager
        available_tiers = list(self.data_manager.accommodation_tiers.values())
        
        # Find the cheapest tier the talent demands (their pickiness is >= requirement)
        demanded_tier_id = None
        for tier in available_tiers:
            if pickiness_score >= tier['pickiness_requirement']:
                demanded_tier_id = tier['id']
                # Because tiers are sorted by cost, the first one they demand is the cheapest they'll demand.
                # However, a very picky talent might demand the most expensive, so we keep checking.
        
        # If they have specific demands, that's what they get.
        if demanded_tier_id:
            return demanded_tier_id

        # If they have no demands, find the most expensive tier they will tolerate (pickiness < requirement)
        # Iterate in reverse (most expensive first) to find the best they'll accept.
        for tier in reversed(available_tiers):
             if pickiness_score < tier['pickiness_requirement']:
                 return tier['id']

        return None # Should not happen if data is configured correctly