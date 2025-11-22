import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass

from data.game_state import Talent, Tour, Scene
from services.models.results import WeeklyStatusResult
from services.models.configs import HiringConfig, TourConfig
from ui.view_models import ScheduleStatus

logger = logging.getLogger(__name__)

class TalentStatusCalculator:
    """
    Centralizes logic for determining a talent's availability status for specific dates.
    Replaces ad-hoc checks in Presenters/UI.
    """
    def __init__(self, hiring_config: HiringConfig, tour_config: TourConfig):
        self.hiring_config = hiring_config
        self.tour_config = tour_config

    def calculate_week_status(self, talent: Talent, week_num: int, current_year: int,
                              bookings: List[Scene], tour: Optional[Tour]) -> WeeklyStatusResult:
        
        tooltip_parts = []
        status_enum = ScheduleStatus.AVAILABLE
        is_on_cooldown = False

        # 1. Check Tour Status
        if tour:
            status_enum = ScheduleStatus.ON_TOUR
            tooltip_parts.append(f"<b>On Tour:</b> {tour.destination_location}")
        
        # 2. Check Cooldown Status (Only if not currently on tour)
        if not tour and talent.tour_end_year > 0:
            abs_current = current_year * 52 + week_num
            abs_end = talent.tour_end_year * 52 + talent.tour_end_week
            
            # Check if within cooldown window
            if abs_end < abs_current <= (abs_end + self.tour_config.cooldown_weeks):
                is_on_cooldown = True
                tooltip_parts.append("<b>Tour Cooldown:</b> Recovering from travel.")

        # 3. Check Fatigue (Resting)
        # Note: This checks current fatigue against the threshold. 
        # In a perfect simulation, we'd project fatigue, but for UI display, current state is standard.
        if talent.fatigue >= self.hiring_config.fatigue_refusal_threshold and not bookings and not tour:
            status_enum = ScheduleStatus.UNAVAILABLE
            tooltip_parts.append("<b>Resting:</b> High Fatigue")

        # 4. Check Booking Capacity
        if bookings:
            scene_titles = [s.title for s in bookings]
            
            # Calculate Max Scenes based on Ambition (Logic moved from Presenter)
            # Logic: Base limit + modifier per ambition level above median
            ambition_bonus = 0
            if talent.ambition > self.hiring_config.median_ambition:
                 # e.g. (Ambition 8 - Median 5) * 0.1 modifier -> +0.3 -> round -> 0 or 1 extra scene
                 bonus_float = (talent.ambition - self.hiring_config.median_ambition) * self.hiring_config.max_scenes_per_week_ambition_modifier
                 ambition_bonus = int(bonus_float) # Simple truncation or logic as desired

            max_scenes = self.hiring_config.max_scenes_per_week_base + ambition_bonus
            
            if len(bookings) >= max_scenes:
                status_enum = ScheduleStatus.UNAVAILABLE
                bulleted_titles = [f"- {title}" for title in scene_titles]
                details = "<br>".join(bulleted_titles)
                tooltip_parts.append(f"<b>Fully Booked:</b><br>{details}")
            else:
                # If not fully booked and not unavailable due to other reasons
                if status_enum == ScheduleStatus.AVAILABLE:
                    status_enum = ScheduleStatus.PARTIALLY_BOOKED
                
                bulleted_titles = [f"- {title}" for title in scene_titles]
                details = "<br>".join(bulleted_titles)
                tooltip_parts.append(f"<b>Booked for:</b><br>{details}")

        return WeeklyStatusResult(
            week_number=week_num,
            status_enum=status_enum,
            tooltip_items=tooltip_parts,
            tour=tour,
            is_on_cooldown=is_on_cooldown
        )