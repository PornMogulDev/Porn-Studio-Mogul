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
    Functions as a sandbox: updates its internal state with every successful check.
    """
    def __init__(self, current_week: int, current_year: int,
                 talent: Talent, existing_bookings: List[Scene],
                 hiring_config: HiringConfig, shoot_calculator: ShootResultsCalculator):
        self.talent = talent
        self.config = hiring_config
        self.shoot_calculator = shoot_calculator
        
        # Initialize state from current talent data
        self.accumulated_fatigue = talent.fatigue
        self.current_week = current_week
        self.current_year = current_year
        self.weekly_counts = defaultdict(int)
        
        for scene in existing_bookings:
            key = (scene.scheduled_year, scene.scheduled_week)
            self.weekly_counts[key] += 1
            
    def try_book_role(self, scene: Scene, vp_id: int) -> ValidationResult:
        year_week_key = (scene.scheduled_year, scene.scheduled_week)
        
        # 1. Check Weekly Limits
        # Priority: Contract > Config
        contract = getattr(self.talent, 'contract', None)
        
        if contract:
            effective_max = contract.max_scenes_per_week
        else:
            ambition = self.talent.ambition
            # Median ambition is roughly 5. Ambition 10 gives +1. Ambition 1 gives -1.
            ambition_bonus = (ambition - self.config.median_ambition) * self.config.max_scenes_per_week_ambition_modifier
            effective_max = max(1, round(self.config.max_scenes_per_week_base + ambition_bonus))
        
        if self.weekly_counts[year_week_key] >= effective_max:
            return ValidationResult(False, f"Weekly limit of {effective_max} scene(s) reached.")
            
        # Logic Fix: Only check fatigue if the scene is happening "now" (current week).
        # Future scenes assume natural fatigue decay will occur, so we rely on the weekly count limit there.
        if scene.scheduled_week == self.current_week and scene.scheduled_year == self.current_year:
            # Calculate estimated gain for this specific role
            estimated_gain = self.shoot_calculator.estimate_fatigue_gain(self.talent, scene, vp_id)
            projected_fatigue = self.accumulated_fatigue + estimated_gain
            
            if projected_fatigue > self.config.fatigue_refusal_threshold:
                return ValidationResult(False, f"Projected fatigue ({projected_fatigue}) exceeds limit.")
            
            # Update accumulated fatigue for subsequent checks in the same batch
            self.accumulated_fatigue = projected_fatigue
            
        # 3. Success - Commit the change to the validator's local state
        self.weekly_counts[year_week_key] += 1
        
        return ValidationResult(True)