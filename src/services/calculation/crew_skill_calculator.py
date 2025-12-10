import random
from typing import Dict, Optional, Any

from data.data_manager import DataManager
from services.calculation.budget_efficiency_calculator import BudgetEfficiencyCalculator
from services.models.configs import ProductionConfig

class CrewSkillCalculator:
    """
    Determines and "rolls" the quality/skill levels for production resources and
    generic crew based on their allocated budget.

    This calculator is responsible for translating a budget allocation into a concrete
    quality score (1-100). It uses the BudgetEfficiencyCalculator to determine a
    base value and then applies a random variance to simulate the unpredictable
    nature of production quality.

    The results are stored in a 'production_cache' on the ShootingBloc, ensuring
    that the quality/skill levels for that bloc are consistent across all its scenes.
    """
    MIN_SCORE = 1
    MAX_SCORE = 100

    def __init__(self, data_manager: DataManager, budget_efficiency_calculator: BudgetEfficiencyCalculator, config: ProductionConfig):
        self.data_manager = data_manager
        self.budget_efficiency_calculator = budget_efficiency_calculator
        self.config = config

    def _get_definition(self, dept_id: str, location_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieves the definition for a department, job, or the dynamic location resource.

        Args:
            dept_id: The ID of the department or job (e.g., 'wardrobe', 'camera_a').
            location_id: The ID of the set location, required to resolve the
                         dynamic 'location_logistics' department.

        Returns:
            The definition dictionary for the item, or None if not found.
        """
        # Check standard departments first
        dept_def = self.data_manager.production_departments.get(dept_id)
        if dept_def:
            return dept_def

        # Check jobs next
        job_def = self.data_manager.production_jobs.get(dept_id)
        if job_def:
            return job_def

        # Handle the dynamic 'location_logistics' department
        if dept_id == 'location_logistics' and location_id:
            loc_def = self.data_manager.production_locations.get(location_id)
            if loc_def:
                return {
                    'id': 'location_logistics',
                    'name': 'Location & Set',
                    'recommended_budget': loc_def.get('recommended_budget', 1000),
                    'min_budget': loc_def.get('min_budget', 0),
                    'curve_type': loc_def.get('curve_type', 'linear')
                }
        
        return None

    def calculate_efficiency_raw(self, dept_def: Dict, budget: int, total_budget: int, visual_style_id: str) -> float:
        """
        Returns the raw budget efficiency multiplier (e.g., 0.8 for low budget, 1.2 for high).

        This value is the direct output of the budget curve calculation before it's
        converted into a 1-100 score. It's used by the UI builder to generate
        real-time estimates for department quality or crew skill.

        Args:
            dept_def: The definition dictionary for the department or job.
            budget: The allocated budget for this specific item (per scene).
            total_budget: The total reference budget for the scene, used for scaling.
            visual_style_id: The ID of the visual style, which can affect efficiency.

        Returns:
            The raw efficiency multiplier as a float.
        """
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
        Generates and persists the quality/skill scores for a shooting bloc.

        This method calculates the final quality score (1-100) for all budgeted
        production resources (e.g., Wardrobe, Props) and generic crew members
        (e.g., Camera Operator, Sound Engineer). It performs a random roll based
        on the budget-derived efficiency, and the results are stored in a
        'production_cache' dictionary for the bloc, ensuring consistent quality
        for all scenes shot within that bloc.

        Args:
            department_budgets: Dict of {dept_id: total_bloc_budget} for resources.
            crew_assignments: Dict of {slot_id: {'type': 'generic', 'budget': ...}}.
            visual_style_def: The definition dictionary for the chosen visual style.
            budget_per_scene: The reference per-scene budget for curve calculation.
            num_scenes: The number of scenes in the bloc, for budget allocation.
            location_id: The ID of the set location, used for the dynamic
                         'location_logistics' department.

        Returns:
            A dictionary mapping department/job IDs to their final rolled score (1-100).
        """
        production_cache = {}
        
        # 1. Process Resources (Departments)
        for dept_id, total_budget in department_budgets.items():
            per_scene_budget = int(total_budget / max(1, num_scenes))
            dept_def = self._get_definition(dept_id, location_id)
            
            if dept_def:
                score = self._roll_score(dept_def, per_scene_budget, budget_per_scene, visual_style_def)
                production_cache[dept_id] = score

        # 2. Process Generic Crew Assignments
        for slot_id, assignment in crew_assignments.items():
            if assignment.get('type') == 'generic':
                total_budget = assignment.get('budget', 0)
                per_scene_budget = int(total_budget / max(1, num_scenes))
                
                job_def = self._get_definition(slot_id) # location_id is not relevant for jobs
                if job_def:
                    score = self._roll_score(job_def, per_scene_budget, budget_per_scene, visual_style_def)
                    production_cache[slot_id] = score
        
        return production_cache

    def _roll_score(self, definition: Dict, budget: int, total_reference_budget: int, visual_style_def: Dict) -> int:
        """
        Calculates the final score for an item based on budget efficiency and random variance.
        
        Args:
            definition: The definition dict for the department or job.
            budget: The per-scene budget for the item.
            total_reference_budget: The total per-scene budget for context.
            visual_style_def: The definition dict for the visual style.

        Returns:
            A final, rolled integer score between MIN_SCORE and MAX_SCORE.
        """
        # 1. Calculate base efficiency from budget
        efficiency = self.budget_efficiency_calculator.calculate_efficiency(
            definition, budget, total_reference_budget, visual_style_def
        )
        
        # 2. Convert to a base score on a 1-100 scale
        base_score = min(self.MAX_SCORE, self.config.crew_skill_baseline_multiplier * efficiency)
        
        # 3. Apply random variance (Gaussian distribution)
        final_score = int(random.gauss(base_score, self.config.crew_skill_sigma))
        
        # 4. Clamp the final score to the defined range
        return max(self.MIN_SCORE, min(self.MAX_SCORE, final_score))