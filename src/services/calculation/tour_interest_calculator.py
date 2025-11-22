import logging
import random
from typing import Optional, Tuple

from data.game_state import Talent
from data.data_manager import DataManager
from services.models.configs import TourConfig
from services.calculation.trait_modifier_resolver import TraitModifierResolver

logger = logging.getLogger(__name__)

class TourInterestCalculator:
    """
    Determines if a talent wants to go on an autonomous tour and selects a destination.
    """
    def __init__(self, trait_resolver: TraitModifierResolver, config: TourConfig, data_manager: DataManager):
        self.trait_resolver = trait_resolver
        self.config = config
        self.data_manager = data_manager

    def calculate_tour_decision(self, talent: Talent, recent_booking_count: int, 
                                current_absolute_week: int) -> Tuple[Optional[str], Optional[int]]:
        """
        Returns (destination, duration) if they want to tour.
        Returns (None, None) if they stay home.
        """
        # 1. Hard Gates
        if talent.is_on_tour:
            return None, None
        
        if talent.fatigue > self.config.autonomous_fatigue_limit:
            return None, None

        # 2. Cooldown Check
        if talent.tour_end_absolute_week > 0:
            weeks_since = current_absolute_week - talent.tour_end_absolute_week
            if weeks_since < self.config.cooldown_weeks:
                return None, None

        # 3. Score Calculation
        score = self.config.base_tour_desire
        score += self.trait_resolver.get_composite_modifier(talent, "tour_desire_flat", default_value=0.0, operation='add')

        normal_load = 4 # 1 per week for the 4 week lookback
        load_delta = normal_load - recent_booking_count
        score += (load_delta * self.config.workload_desire_modifier)
        score += random.uniform(-15, 15)

        # 4. Decision
        if score > self.config.tour_desire_threshold:
            destination = self._pick_destination(talent)
            duration = random.randint(self.config.min_tour_duration, self.config.max_tour_duration)
            return destination, duration

        return None, None

    def _pick_destination(self, talent: Talent) -> str:
        """
        Picks a random location that is NOT the talent's current base.
        Once we add AI studios and location picking for blocks/scenes, we should
        give each location a booking history of sorts to make this not completely random.
        """
        all_locations = list(self.data_manager.get_location_to_region_map().keys())
        valid_locations = [loc for loc in all_locations if loc != talent.base_location]
        
        if not valid_locations:
            return "South West (US)" # Fallback
            
        return random.choice(valid_locations)