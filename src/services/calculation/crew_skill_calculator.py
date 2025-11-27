import random
from typing import Dict, Union, Optional

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

    def calculate_base_efficiency(self, dept_or_def: Union[str, Dict], budget: int, total_budget: int, visual_style_id: str) -> float:
        """
        Calculates the raw base skill/quality score (0-100) for a department 
        BEFORE random variance is applied. Used for UI estimates.
        Accepts either a department ID (str) or a definition dict.
        """
        if isinstance(dept_or_def, dict):
            dept_def = dept_or_def
        else:
            # Look up by ID
            dept_def = self.data_manager.production_departments.get(dept_or_def)
            if not dept_def:
                dept_def = self.data_manager.production_jobs.get(dept_or_def)

        style_def = self.data_manager.visual_styles.get(visual_style_id)

        if not dept_def or not style_def:
            # If still not found, return 0
            return 0.0

        efficiency = self.budget_efficiency_calculator.calculate_efficiency(
            dept_def, budget, total_budget, style_def
        )

        # Convert to Base Skill (0-100)
        return min(100.0, self.config.crew_skill_baseline_multiplier * efficiency)

    def generate_resolved_skills(self, 
                                 department_budgets: Dict[str, int], 
                                 production_departments: Dict[str, Dict],
                                 visual_style_def: Dict,
                                 location_id: Optional[str] = None) -> Dict[str, int]:
        """
        Returns a dictionary of {department_id: skill_level (0-100)} for all 
        departments flagged as having 'skill_cap' or 'execution_quality' impacts.
        """
        total_budget = sum(department_budgets.values())
        resolved_skills = {}

        # FIX: We need to iterate over JOBS as well, as this is primarily for Crew
        # Merging definitions for iteration logic
        all_defs = {**self.data_manager.production_departments, **self.data_manager.production_jobs}

        for dept_id, dept_def in all_defs.items():
            impacts = dept_def.get("impacts", [])
            
            # Only generate skills for entities that have skill/quality impacts
            if "skill_cap" in impacts or "execution_quality" in impacts:
                
                budget = department_budgets.get(dept_id, 0)
                
                # 1. Calculate Efficiency
                efficiency = self.budget_efficiency_calculator.calculate_efficiency(
                    dept_def, budget, total_budget, visual_style_def
                )
                
                # 2. Convert to Base Skill (0-100)
                base_skill = min(100, self.config.crew_skill_baseline_multiplier * efficiency)
                
                # 3. Apply Random Variance (Gaussian)
                final_skill = int(random.gauss(base_skill, self.config.crew_skill_sigma))
                final_skill = max(1, min(100, final_skill))
                
                resolved_skills[dept_id] = final_skill

        # Handle Location Logistics (Dynamic)
        if location_id and 'location_logistics' in department_budgets:
            loc_def = self.data_manager.production_locations.get(location_id)
            if loc_def:
                # Create virtual definition matching Schema
                virtual_def = {
                    'id': 'location_logistics',
                    'recommended_budget': loc_def.get('recommended_budget', 1000),
                    'min_budget': loc_def.get('min_budget', 0),
                    'curve_type': loc_def.get('curve_type', 'linear')
                }
                budget = department_budgets['location_logistics']
                efficiency = self.budget_efficiency_calculator.calculate_efficiency(
                    virtual_def, budget, total_budget, visual_style_def
                )
                base_quality = self.config.crew_skill_baseline_multiplier * efficiency
                resolved_skills['location_logistics'] = min(100, int(base_quality))
        
        return resolved_skills