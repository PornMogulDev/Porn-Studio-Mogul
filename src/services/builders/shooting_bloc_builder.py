import logging
import math
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from data.data_manager import DataManager
from services.models.configs import ProductionConfig
from services.calculation.crew_skill_calculator import CrewSkillCalculator
from services.calculation.bloc_cost_calculator import BlocCostCalculator

logger = logging.getLogger(__name__)

@dataclass
class DepartmentState:
    id: str
    name: str
    allocation_percent: float # 0.0 to 1.0
    is_locked: bool = False
    min_budget: int = 0
    type: str = "resource" # 'crew' or 'resource'

class ShootingBlocBuilder:
    """
    Stateful service for constructing a Shooting Bloc configuration.
    
    Responsibilities:
    1. Manages Total Budget and Percentage Allocations for departments.
    2. Handles "Slider Logic": adjusting one slider redistributes the delta 
       proportionally among unlocked sliders to maintain a 1.0 (100%) sum.
    3. Provides live previews of Estimated Crew Skills based on current allocations.
    4. Validates configuration before commit.
    """

    def __init__(self, 
                 data_manager: DataManager, 
                 production_config: ProductionConfig,
                 crew_skill_calculator: CrewSkillCalculator,
                 bloc_cost_calculator: BlocCostCalculator):
        
        self.data_manager = data_manager
        self.config = production_config
        self.crew_calculator = crew_skill_calculator
        self.cost_calculator = bloc_cost_calculator

        # -- State --
        self.total_budget: int = 5000
        self.region_id: str = "south_west_us" # Default
        self.location_id: Optional[str] = None
        self.visual_style_id: str = "glossy" # Default
        self.active_policies: List[str] = []
        
        # Departments State (Key: dept_id, Value: DepartmentState)
        self.departments: Dict[str, DepartmentState] = {}
        
        self._initialize_departments()

    def _initialize_departments(self):
        """Loads definitions and sets default even spread."""
        dept_defs = self.data_manager.production_departments
        if not dept_defs:
            logger.error("No production departments found in DataManager.")
            return

        # 1. Load Defaults
        count = len(dept_defs)
        default_split = 1.0 / count if count > 0 else 0
        
        running_total = 0.0
        
        for i, (dept_id, defs) in enumerate(dept_defs.items()):
            # Use defined base_weight if exists, otherwise even split, normalize later
            raw_weight = defs.get('base_weight', default_split)
            
            self.departments[dept_id] = DepartmentState(
                id=dept_id,
                name=defs.get('name', dept_id.title()),
                allocation_percent=raw_weight,
                min_budget=defs.get('min_budget', 0),
                type=defs.get('type', 'resource')
            )
            running_total += raw_weight

        # 2. Normalize to exactly 1.0
        if running_total > 0:
            for dept in self.departments.values():
                dept.allocation_percent /= running_total
        
        # Ensure floating point clean-up
        self._normalize_rounding_errors()

    def set_total_budget(self, amount: int):
        """Sets the raw money available for the departments."""
        self.total_budget = max(500, amount) # Minimum floor

    def set_logistics(self, region_id: str, location_id: str, visual_style_id: str):
        self.region_id = region_id
        self.location_id = location_id
        self.visual_style_id = visual_style_id

    def toggle_policy(self, policy_id: str, is_active: bool):
        if is_active and policy_id not in self.active_policies:
            self.active_policies.append(policy_id)
        elif not is_active and policy_id in self.active_policies:
            self.active_policies.remove(policy_id)

    def toggle_lock(self, dept_id: str, is_locked: bool):
        if dept_id in self.departments:
            self.departments[dept_id].is_locked = is_locked

    def update_allocation(self, target_dept_id: str, new_percent: float) -> bool:
        """
        The core logic. Attempts to set a specific department to a new percentage.
        Automatically adjusts other unlocked departments to keep sum at 1.0.
        
        Returns False if the change is impossible (e.g., all others locked).
        """
        if target_dept_id not in self.departments:
            return False

        target = self.departments[target_dept_id]
        
        # Clamp input 0.0 to 1.0
        new_percent = max(0.0, min(1.0, new_percent))
        
        current_percent = target.allocation_percent
        if math.isclose(new_percent, current_percent):
            return True

        delta = new_percent - current_percent
        
        # Identify the pool of departments that can absorb the change
        # (Not the target, and not locked)
        absorb_pool = [
            d for d in self.departments.values() 
            if d.id != target_dept_id and not d.is_locked
        ]

        if not absorb_pool:
            # Cannot change if everyone else is locked
            return False

        # Calculate total available in pool
        pool_sum = sum(d.allocation_percent for d in absorb_pool)

        # Check: If delta is positive (taking money), do we have enough in pool?
        # Note: If pool_sum is 0, we can't take anything from them.
        if delta > 0 and delta > pool_sum:
            # Cap the new_percent to what is available
            new_percent = current_percent + pool_sum
            delta = new_percent - current_percent

        # Apply change to target
        target.allocation_percent = new_percent

        # Distribute -delta across pool
        # If pool_sum is 0 (all at 0%), we divide evenly. Otherwise proportionally.
        remaining_delta = -delta # We need to remove this amount from pool
        
        for dept in absorb_pool:
            if pool_sum > 0.001:
                # Proportional share
                share = dept.allocation_percent / pool_sum
                change = remaining_delta * share
            else:
                # Even share (if everyone was 0)
                change = remaining_delta / len(absorb_pool)
            
            dept.allocation_percent = max(0.0, dept.allocation_percent + change)

        self._normalize_rounding_errors()
        return True

    def _normalize_rounding_errors(self):
        """Ensures the sum is exactly 1.0 by dumping dust into the largest unlocked dept."""
        total = sum(d.allocation_percent for d in self.departments.values())
        diff = 1.0 - total
        
        if not math.isclose(diff, 0.0):
            # Add diff to the largest unlocked department to minimize visual jump
            # If all locked, add to target (shouldn't happen in valid flow)
            candidates = [d for d in self.departments.values() if not d.is_locked]
            if not candidates:
                candidates = list(self.departments.values())
            
            # Sort by size desc
            candidates.sort(key=lambda d: d.allocation_percent, reverse=True)
            candidates[0].allocation_percent += diff
            # Ensure no negative from dust adjustment
            candidates[0].allocation_percent = max(0.0, candidates[0].allocation_percent)

    # --- Query Methods for UI ---

    def get_allocation_data(self) -> Dict[str, Dict[str, Any]]:
        """Returns data for UI rendering (percentages and real dollar amounts)."""
        result = {}
        for dept in self.departments.values():
            budget = int(self.total_budget * dept.allocation_percent)
            result[dept.id] = {
                "name": dept.name,
                "percent": dept.allocation_percent,
                "amount": budget,
                "is_locked": dept.is_locked,
                "is_below_min": budget < dept.min_budget
            }
        return result

    def get_estimates(self) -> Dict[str, Any]:
        """
        Returns estimated results (Skill levels for crew, Quality tiers for resources).
        Used for UI tooltips/labels updates.
        """
        estimates = {}
        style_def = self.data_manager.visual_styles.get(self.visual_style_id, {})
        
        for dept in self.departments.values():
            budget = int(self.total_budget * dept.allocation_percent)
            
            if dept.type == 'crew':
                # Use calculator to get range
                base_skill = self.crew_calculator.calculate_base_efficiency(
                    dept.id, budget, self.total_budget, self.visual_style_id
                )
                # Show a range due to random variance
                variance = self.config.crew_skill_sigma * 2
                min_skill = max(0, int(base_skill - variance))
                max_skill = min(100, int(base_skill + variance))
                estimates[dept.id] = f"{min_skill}-{max_skill} Skill"
            else:
                # Resource: Convert directly to a quality adjective or score
                # This could be moved to a specific calculator if complex
                quality_score = self.crew_calculator.calculate_base_efficiency(
                    dept.id, budget, self.total_budget, self.visual_style_id
                )
                estimates[dept.id] = f"Quality: {int(quality_score)}"
                
        return estimates

    def get_total_cost(self, num_scenes: int) -> int:
        """Calculates total upfront cost."""
        # Create temporary dicts for calculator
        budget_map = {d_id: int(self.total_budget * d.allocation_percent) 
                      for d_id, d in self.departments.items()}
        
        # Pass a 'Generic' crew assignment map for now (cost is in the budget map)
        # In this model, the budget IS the cost.
        
        # We need to add Location Cost + Policy Costs
        # Note: BlocCostCalculator expects department_budgets as total for block
        
        return self.cost_calculator.calculate_shooting_bloc_cost(
            location_id=self.location_id,
            department_budgets=budget_map,
            crew_assignments={}, # Handled via department budgets in this new model
            picture_set_settings={},
            policies=self.active_policies
        )

    def commit(self, name: str, scheduled_week: int, num_scenes: int) -> Dict[str, Any]:
        """
        Finalizes the builder state and returns the data dictionary required 
        by SceneCommandService to create the persistent entity.
        """
        allocations = {d.id: d.allocation_percent for d in self.departments.values()}
        locked = [d.id for d in self.departments.values() if d.is_locked]
        
        budget_data = {
            "total_budget": self.total_budget,
            "allocations": allocations,
            "locked_departments": locked
        }
        
        logistics = {
            "region_id": self.region_id,
            "location_id": self.location_id,
            "visual_style_id": self.visual_style_id
        }
        
        return {
            "name": name,
            "scheduled_absolute_week": scheduled_week,
            "num_scenes": num_scenes,
            "logistics": logistics,
            "budget_data": budget_data,
            "policies": self.active_policies
        }