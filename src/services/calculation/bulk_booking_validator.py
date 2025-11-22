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
        self.talent = talent
        self.config = hiring_config
        self.shoot_calculator = shoot_calculator
        
        self.accumulated_fatigue = talent.fatigue
        self.current_absolute_week = current_absolute_week
        self.weekly_counts = defaultdict(int)
        
        for scene in existing_bookings:
            self.weekly_counts[scene.scheduled_absolute_week] += 1
            
    def try_book_role(self, scene: Scene, vp_id: int) -> ValidationResult:
        absolute_week_key = scene.scheduled_absolute_week
        
        contract = getattr(self.talent, 'contract', None)
        
        if contract:
            effective_max = contract.max_scenes_per_week
        else:
            ambition_bonus = (self.talent.ambition - self.config.median_ambition) * self.config.max_scenes_per_week_ambition_modifier
            effective_max = max(1, round(self.config.max_scenes_per_week_base + ambition_bonus))
        
        if self.weekly_counts[absolute_week_key] >= effective_max:
            return ValidationResult(False, f"Weekly limit of {effective_max} scene(s) reached.")
            
        if absolute_week_key == self.current_absolute_week:
            estimated_gain = self.shoot_calculator.estimate_fatigue_gain(self.talent, scene, vp_id)
            projected_fatigue = self.accumulated_fatigue + estimated_gain
            
            if projected_fatigue > self.config.fatigue_refusal_threshold:
                return ValidationResult(False, f"Projected fatigue ({projected_fatigue}) exceeds limit.")
            
            self.accumulated_fatigue = projected_fatigue
            
        self.weekly_counts[absolute_week_key] += 1
        
        return ValidationResult(True)