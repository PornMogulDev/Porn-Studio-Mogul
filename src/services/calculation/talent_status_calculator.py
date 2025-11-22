import logging
from typing import List, Optional

from data.game_state import Talent, Tour, Scene
from services.models.results import WeeklyStatusResult
from services.models.configs import HiringConfig, TourConfig
from ui.view_models import ScheduleStatus
from utils import time_utils

logger = logging.getLogger(__name__)

class TalentStatusCalculator:
    """
    Centralizes logic for determining a talent's availability status for specific dates.
    Replaces ad-hoc checks in Presenters/UI.
    """
    def __init__(self, hiring_config: HiringConfig, tour_config: TourConfig):
        self.hiring_config = hiring_config
        self.tour_config = tour_config

    def calculate_week_status(self, talent: Talent, absolute_week: int,
                              bookings: List[Scene], tour: Optional[Tour]) -> WeeklyStatusResult:
        
        booked_scene_titles = []
        status_enum = ScheduleStatus.AVAILABLE
        is_on_cooldown = False
        is_fatigued = False

        # 1. Check Tour Status
        if tour:
            status_enum = ScheduleStatus.ON_TOUR
        
        # 2. Check Cooldown Status (Only if not currently on tour)
        if not tour and talent.tour_end_absolute_week > 0:
            end_abs = talent.tour_end_absolute_week
            
            # Check if within cooldown window
            if end_abs < absolute_week <= (end_abs + self.tour_config.cooldown_weeks):
                is_on_cooldown = True

        # 3. Check Fatigue (Resting)
        if talent.fatigue >= self.hiring_config.fatigue_refusal_threshold and not bookings and not tour:
            status_enum = ScheduleStatus.UNAVAILABLE
            is_fatigued = True

        # 4. Check Booking Capacity
        if bookings:
            booked_scene_titles = [s.title for s in bookings]
            
            ambition_bonus = 0
            if talent.ambition > self.hiring_config.median_ambition:
                 bonus_float = (talent.ambition - self.hiring_config.median_ambition) * self.hiring_config.max_scenes_per_week_ambition_modifier
                 ambition_bonus = int(bonus_float)

            max_scenes = self.hiring_config.max_scenes_per_week_base + ambition_bonus
            
            if len(bookings) >= max_scenes:
                status_enum = ScheduleStatus.UNAVAILABLE
            else:
                if status_enum == ScheduleStatus.AVAILABLE:
                    status_enum = ScheduleStatus.PARTIALLY_BOOKED

        _year, week_num = time_utils.from_absolute(absolute_week)
        return WeeklyStatusResult(
            week_number=week_num,
            status_enum=status_enum,
            booked_scene_titles=booked_scene_titles,
            tour=tour,
            is_on_cooldown=is_on_cooldown,
            is_fatigued=is_fatigued
        )