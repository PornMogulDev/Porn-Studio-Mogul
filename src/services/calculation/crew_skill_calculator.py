import random
from typing import Dict

from data.data_manager import DataManager
from services.calculation.budget_efficiency_calculator import BudgetEfficiencyCalculator
from services.models.configs import ProductionConfig

class CrewSkillCalculator:
    """
    Determines the specific skill levels for crew positions based on budget allocations,
    visual style efficiency, and random variance (simulating the hiring market).
    """
    def __init__(self, data_manager: DataManager, budget_efficiency_calculator: BudgetEfficiencyCalculator, config: ProductionConfig):
        self.data_manager = data_manager
        self.budget_efficiency_calculator = budget_efficiency_calculator
        self.config = config

    def calculate_base_efficiency(self, dept_id: str, budget: int, total_budget: int, visual_style_id: str) -> float:
        """
        Calculates the raw base skill/quality score (0-100) for a department 
        BEFORE random variance is applied. Used for UI estimates.
        """
        dept_def = self.data_manager.production_departments.get(dept_id)
        style_def = self.data_manager.visual_styles.get(visual_style_id)

        if not dept_def or not style_def:
            return 0.0

        efficiency = self.budget_efficiency_calculator.calculate_efficiency(
            dept_def, budget, total_budget, style_def
        )

        # Convert to Base Skill (0-100)
        return min(100.0, self.config.crew_skill_baseline_multiplier * efficiency)

    def generate_resolved_skills(self, 
                                 department_budgets: Dict[str, int], 
                                 production_departments: Dict[str, Dict],
                                 visual_style_def: Dict) -> Dict[str, int]:
        """
        Returns a dictionary of {department_id: skill_level (0-100)} for all 
        departments flagged as having 'skill_cap' or 'execution_quality' impacts.
        """
        total_budget = sum(department_budgets.values())
        resolved_skills = {}

        for dept_id, dept_def in production_departments.items():
            impacts = dept_def.get("impacts", [])
            # Only generate skills for "Crew" type departments (Director, Camera, etc)
            if "skill_cap" in impacts or "execution_quality" in impacts:
                
                budget = department_budgets.get(dept_id, 0)
                
                # 1. Calculate Efficiency (0.1 to ~1.5+)
                efficiency = self.budget_efficiency_calculator.calculate_efficiency(
                    dept_def, budget, total_budget, visual_style_def
                )
                
                # 2. Convert to Base Skill (0-100)
                # Efficiency 1.0 = Skill 50 (Average Pro), 1.5 = Skill 75+
                base_skill = min(100, self.config.crew_skill_baseline_multiplier * efficiency)
                
                # 3. Apply Random Variance (Gaussian)
                # Simulates that sometimes you hire a genius for cheap, or a dud for $$$.
                final_skill = int(random.gauss(base_skill, self.config.crew_skill_sigma))
                final_skill = max(1, min(100, final_skill))
                
                resolved_skills[dept_id] = final_skill
        
        return resolved_skills