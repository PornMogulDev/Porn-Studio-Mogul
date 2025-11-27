import random
from typing import Dict, Union, Optional, Any

from data.data_manager import DataManager
from services.calculation.budget_efficiency_calculator import BudgetEfficiencyCalculator
from services.models.configs import ProductionConfig

class CrewSkillCalculator:
    """
    Determines the specific skill/quality levels for production slots (Resources & Generic Crew).
    Generates the 'production_cache' which persists these rolls for the duration of the bloc.
    """
    def __init__(self, data_manager: DataManager, budget_efficiency_calculator: BudgetEfficiencyCalculator, config: ProductionConfig):
        self.data_manager = data_manager
        self.budget_efficiency_calculator = budget_efficiency_calculator
        self.config = config

    def calculate_efficiency_raw(self, dept_or_def: Union[str, Dict], budget: int, total_budget: int, visual_style_id: str) -> float:
        """
        Returns the raw efficiency multiplier (e.g. 0.8, 1.2) without scaling to 0-100 skill.
        Used by the UI Builder to generate estimates without double-applying multipliers.
        """
        if isinstance(dept_or_def, dict):
            dept_def = dept_or_def
        else:
            dept_def = self.data_manager.production_departments.get(dept_or_def)
            if not dept_def:
                dept_def = self.data_manager.production_jobs.get(dept_or_def)

        style_def = self.data_manager.visual_styles.get(visual_style_id)

        if not dept_def or not style_def:
            return 0.0

        return self.budget_efficiency_calculator.calculate_efficiency(
            dept_def, budget, total_budget, style_def
        )

    def generate_production_cache(self, 
                                 department_budgets: Dict[str, int], 
                                 crew_assignments: Dict[str, Dict[str, Any]],
                                 visual_style_def: Dict,
                                 budget_per_scene: int,
                                 num_scenes: int,
                                 location_id: Optional[str] = None) -> Dict[str, int]:
        """
        Generates the production cache: a dictionary of {slot_id: final_score (0-100)}.
        This includes Resources (Departments) and Generic Crew assignments.
        
        Args:
            department_budgets: Dict of {dept_id: total_bloc_budget} for resources.
            crew_assignments: Dict of {slot_id: {'type': 'generic', 'budget': total_bloc_budget, ...}}
            budget_per_scene: The reference per-scene budget for curve calculation.
        """
        production_cache = {}
        
        # 1. Process Resources (Departments)
        for dept_id, total_budget in department_budgets.items():
            # Calculate per-scene amount for curve logic
            per_scene_budget = int(total_budget / max(1, num_scenes))
            
            # Retrieve definition (Standard or Dynamic Location)
            dept_def = self.data_manager.production_departments.get(dept_id)
            
            # Special handling for Location Logistics if not in standard departments
            if dept_id == 'location_logistics' and not dept_def and location_id:
                 loc_def = self.data_manager.production_locations.get(location_id)
                 if loc_def:
                     dept_def = {
                        'id': 'location_logistics',
                        'recommended_budget': loc_def.get('recommended_budget', 1000),
                        'min_budget': loc_def.get('min_budget', 0),
                        'curve_type': loc_def.get('curve_type', 'linear')
                    }
            
            if dept_def:
                score = self._roll_score(dept_def, per_scene_budget, budget_per_scene, visual_style_def)
                production_cache[dept_id] = score

        # 2. Process Generic Crew Assignments
        for slot_id, assignment in crew_assignments.items():
            if assignment.get('type') == 'generic':
                job_def = self.data_manager.production_jobs.get(slot_id)
                if not job_def: continue
                
                total_budget = assignment.get('budget', 0)
                per_scene_budget = int(total_budget / max(1, num_scenes))
                
                score = self._roll_score(job_def, per_scene_budget, budget_per_scene, visual_style_def)
                production_cache[slot_id] = score
        
        return production_cache

    def _roll_score(self, definition: Dict, budget: int, total_reference_budget: int, visual_style_def: Dict) -> int:
        """Helper to calculate efficiency and apply RNG variance."""
        # 1. Calculate Efficiency
        efficiency = self.budget_efficiency_calculator.calculate_efficiency(
            definition, budget, total_reference_budget, visual_style_def
        )
        
        # 2. Convert to Base Skill (0-100)
        base_skill = min(100, self.config.crew_skill_baseline_multiplier * efficiency)
        
        # 3. Apply Random Variance (Gaussian)
        final_skill = int(random.gauss(base_skill, self.config.crew_skill_sigma))
        
        return max(1, min(100, final_skill))