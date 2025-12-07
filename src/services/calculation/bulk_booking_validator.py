import logging
from collections import defaultdict
from typing import List


from data.game_state import Talent, Scene
from services.models.configs import HiringConfig
from services.models.results import ValidationResult
from services.calculation.shoot_results_calculator import ShootResultsCalculator

logger = logging.getLogger(__name__)

class BulkBookingValidator:
    """
    Validates a sequence of role additions for a talent to prevent
    exceeding weekly limits or fatigue thresholds.
    """
    def __init__(self, current_absolute_week: int,
                 talent: Talent, existing_bookings: List[Scene],
                 hiring_config: HiringConfig, shoot_calculator: ShootResultsCalculator):
        """
        Initializes the validator with the talent's current state and bookings.

        Args:
            current_absolute_week: The game's current absolute week for fatigue calculations.
            talent: The talent dataclass for whom the bookings are being validated.
            existing_bookings: A list of Scene dataclasses the talent is already booked for.
            hiring_config: Configuration for hiring rules (e.g., fatigue limits).
            shoot_calculator: Service to estimate fatigue gain.
        """
        from utils import time_utils

        self.talent = talent
        self.config = hiring_config
        self.shoot_calculator = shoot_calculator
        
        self.accumulated_fatigue = talent.fatigue
        self.current_absolute_week = current_absolute_week
        self.weekly_counts = defaultdict(int)
        self.monthly_counts = defaultdict(int)
        
        for scene in existing_bookings:
            self.weekly_counts[scene.scheduled_absolute_week] += 1
            year, month, _ = time_utils.to_month(scene.scheduled_absolute_week)
            self.monthly_counts[(year, month)] += 1
            
    def try_book_role(self, scene: Scene, vp_id: int) -> ValidationResult:
        """
        Attempts to validate a single role booking.
        
        This method is stateful. If validation succeeds, it internally updates
        its weekly booking count and projected fatigue for subsequent calls.

        Args:
            scene: The Scene dataclass the talent would be booked in.
            vp_id: The virtual performer ID within the scene.

        Returns:
            A ValidationResult indicating success or failure with a reason.
        """
        import math
        from utils import time_utils
        
        absolute_week_key = scene.scheduled_absolute_week
        year, month, _ = time_utils.to_month(absolute_week_key)
        
        contract = getattr(self.talent, 'contract', None)
        
        if contract:
            # 1. Bounds Check: Is the booking actually inside the contract duration?
            contract_start = contract.start_absolute_week
            # Note: duration is inclusive (e.g., start 1, duration 1 covers only week 1)
            contract_end = contract_start + contract.duration_weeks - 1
            
            if not (contract_start <= absolute_week_key <= contract_end):
                return ValidationResult(False, "Booking date falls outside the contract duration.")

            # 2. Proration Check: Calculate effective limit for this specific month
            # Get the boundaries of the calendar month (e.g., Week 5 to Week 8)
            month_start_week, month_end_week = time_utils.get_month_range(absolute_week_key)
            
            # Calculate intersection of [MonthStart, MonthEnd] and [ContractStart, ContractEnd]
            effective_start = max(month_start_week, contract_start)
            effective_end = min(month_end_week, contract_end)
            
            # How many weeks is the contract active during this calendar month?
            # e.g., if contract starts Week 3 of a 4-week month, active_weeks = 2 (Weeks 3 & 4)
            active_weeks_in_month = max(0, (effective_end - effective_start) + 1)
            
            # Calculate ratio based on standard 4-week month (from time_utils)
            proration_factor = active_weeks_in_month / 4.0 
            
            # Calculate final limit using ceil to be generous (e.g., limit 4 * 0.25 = 1 scene allowed)
            effective_monthly_limit = math.ceil(contract.max_scenes_per_month * proration_factor)
            
            if self.monthly_counts[(year, month)] >= effective_monthly_limit:
                msg = f"Monthly limit reached ({effective_monthly_limit} allowed this month)."
                if proration_factor < 1.0:
                    msg += " (Limit reduced due to partial month contract coverage)"
                return ValidationResult(False, msg)

        else:
            # Standard Weekly Logic for non-contracted talent
            ambition_bonus = (self.talent.ambition - self.config.median_ambition) * self.config.max_scenes_per_week_ambition_modifier
            effective_max = max(1, round(self.config.max_scenes_per_week_base + ambition_bonus))
            
            if self.weekly_counts[absolute_week_key] >= effective_max:
                return ValidationResult(False, f"Weekly limit of {effective_max} scene(s) reached.")
            
        # Fatigue Check (Applies to everyone)
        # Note: We only check projection for the *current* week to prevent immediate exhaustion.
        # Future fatigue is harder to predict due to rest weeks.
        if absolute_week_key == self.current_absolute_week:
            estimated_gain = self.shoot_calculator.estimate_fatigue_gain(self.talent, scene, vp_id)
            projected_fatigue = self.accumulated_fatigue + estimated_gain
            
            if projected_fatigue > self.config.fatigue_refusal_threshold:
                return ValidationResult(False, f"Projected fatigue ({projected_fatigue}) exceeds limit.")
            
            self.accumulated_fatigue = projected_fatigue
            
        # Update State (Count the booking)
        self.weekly_counts[absolute_week_key] += 1
        self.monthly_counts[(year, month)] += 1
        
        return ValidationResult(True)