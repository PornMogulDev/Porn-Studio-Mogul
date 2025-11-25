from typing import List, Dict
from data.game_state import Talent
from data.data_manager import DataManager
from services.models.configs import SceneCalculationConfig

class StressCalculator:
    """
    Calculates stress accumulation for talents based on roles, environment, and support.
    """
    def __init__(self, data_manager: DataManager, config: SceneCalculationConfig):
        self.data_manager = data_manager
        self.config = config

    def calculate_stress_gain(self, 
                              talent: Talent, 
                              jobs: List[str], 
                              location_def: Dict, 
                              craft_services_efficiency: float,
                              events_modifier: float = 0.0) -> float:
        """
        Calculates stress gain for a single bloc/scene.
        """
        base_stress = 0.0
        
        # 1. Role Stress
        for job_id in jobs:
            if job_id == 'actor':
                base_stress += self.config.base_acting_stress
            else:
                job_def = self.data_manager.production_jobs.get(job_id)
                if job_def:
                    base_stress += job_def.get('base_stress_load', 5)

        # 2. Multitasking Penalty
        role_count = len(jobs)
        multitask_multiplier = 1.0
        
        if role_count > 1 and "Workaholic" not in talent.traits:
            # e.g., 2 roles = 1 + (1 * 0.5) = 1.5x
            multitask_multiplier = 1.0 + ((role_count - 1) * self.config.multitasking_stress_multiplier)
            
        total_stress = base_stress * multitask_multiplier

        # 3. Location Modifiers
        loc_mods = location_def.get('simulation_modifiers', {})
        location_stress = loc_mods.get('base_stress', 0)
        
        # Apply traits interacting with location
        # TODO: Move trait name to config/constants eventually
        if "Introvert" in talent.traits and "Public" in location_def.get('tags', []):
            location_stress += self.config.introvert_crowd_penalty
        
        total_stress += location_stress

        # 4. Support Reduction (Craft Services)
        stress_relief = craft_services_efficiency * self.config.craft_services_stress_relief_scalar
        total_stress -= stress_relief

        # 5. Events
        total_stress += events_modifier

        return max(0.0, total_stress)