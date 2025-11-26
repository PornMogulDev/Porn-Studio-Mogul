import logging
import math
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from data.data_manager import DataManager
from services.models.configs import ProductionConfig
from services.calculation.crew_skill_calculator import CrewSkillCalculator
from services.calculation.bloc_cost_calculator import BlocCostCalculator

logger = logging.getLogger(__name__)

@dataclass
class DepartmentState:
    id: str
    name: str
    percent: float # 0.0 to 1.0
    user_locked: bool = False
    system_disabled: bool = False
    min_budget: int = 0
    type: str = "resource" 

class ShootingBlocBuilder:
    def __init__(self, 
                 data_manager: DataManager, 
                 production_config: ProductionConfig,
                 crew_skill_calculator: CrewSkillCalculator,
                 bloc_cost_calculator: BlocCostCalculator):
        
        self.data_manager = data_manager
        self.config = production_config
        self.crew_calculator = crew_skill_calculator
        self.cost_calculator = bloc_cost_calculator

        # State Variables
        self.budget_per_scene: int = 2500
        self.num_scenes: int = 2
        
        self.region_id: str = "south_west_us"
        self.location_id: Optional[str] = None
        self.visual_style_id: str = "glossy"
        self.active_policies: List[str] = []

        self.picture_set_type_id: str = "video_grabs"
        self.camera_count: int = 1
        self.camera_mounts: List[str] = ["Handheld", "Tripod", "Tripod"] 

        # Departments
        self.departments: Dict[str, DepartmentState] = {}
        
        self._initialize_departments()
        
    def _initialize_departments(self):
        """Initial loading of departments. Happens once."""
        resource_defs = self.data_manager.production_departments
        crew_defs = self.data_manager.production_jobs
        
        # Merge and create states
        all_defs = []
        if resource_defs:
            for k, v in resource_defs.items():
                all_defs.append((k, v, 'resource'))
        if crew_defs:
            for k, v in crew_defs.items():
                all_defs.append((k, v, 'crew'))
                
        # Calculate initial even split
        count = len(all_defs)
        split = 1.0 / count if count > 0 else 0.0
        
        for dept_id, defs, d_type in all_defs:
            # Check JSON for base_weight, else use split
            # Note: Current JSONs have base_weight for resources, but maybe not jobs
            weight = defs.get('base_weight', split)
            
            self.departments[dept_id] = DepartmentState(
                id=dept_id,
                name=defs.get('name', dept_id.title()),
                percent=weight,
                min_budget=defs.get('min_budget', 0),
                type=d_type
            )
            
        # Initial normalization to ensure 1.0 sum
        self._normalize_sum()
        # Apply initial system locks (e.g. disable photographer if default is video grabs)
        self._apply_system_constraints()

    # --- Configuration Setters ---

    def set_budget_per_scene(self, amount: int):
        self.budget_per_scene = max(0, amount)

    def set_num_scenes(self, count: int):
        self.num_scenes = max(1, count)

    def set_logistics(self, region_id: str, location_id: str, visual_style_id: str):
        self.region_id = region_id
        self.location_id = location_id
        self.visual_style_id = visual_style_id

    def set_picture_set_type(self, type_id: str):
        self.picture_set_type_id = type_id
        self._apply_system_constraints()

    def set_camera_config(self, count: int, mounts: List[str]):
        self.camera_count = count
        self.camera_mounts = (mounts + ["Tripod"] * 3)[:3]
        self._apply_system_constraints()

    def toggle_policy(self, policy_id: str, is_active: bool):
        if is_active and policy_id not in self.active_policies:
            self.active_policies.append(policy_id)
        elif not is_active and policy_id in self.active_policies:
            self.active_policies.remove(policy_id)

    # --- Core Logic: Constraints & Allocations ---

    def _apply_system_constraints(self):
        """Enables/Disables departments based on camera/picture settings."""
        
        # 1. Determine what should be disabled
        to_disable = set()

        # Photographer
        pst_def = self.data_manager.picture_set_types.get(self.picture_set_type_id, {})
        if not pst_def.get('requires_photographer', False):
            to_disable.add('photographer')

        # Cameras
        if self.camera_mounts[0] == "Tripod": 
            to_disable.add('camera_a') # Static
        
        if self.camera_count < 2 or self.camera_mounts[1] == "Tripod":
            to_disable.add('camera_b')

        # 2. Apply State Changes
        redistribution_needed = False
        
        for dept in self.departments.values():
            should_be_disabled = dept.id in to_disable
            
            if should_be_disabled and not dept.system_disabled:
                # Transition: Active -> Disabled
                # Set percent to 0, flag for redistribution
                dept.percent = 0.0
                dept.system_disabled = True
                redistribution_needed = True
                
            elif not should_be_disabled and dept.system_disabled:
                # Transition: Disabled -> Active
                # Enable it, but keep percent at 0.0. User must drag it up.
                dept.system_disabled = False
                dept.percent = 0.0
                # No redistribution needed immediately, sum is still valid (assuming it was valid)
                
        if redistribution_needed:
            self._normalize_sum()

    def toggle_user_lock(self, dept_id: str, is_locked: bool):
        if dept_id in self.departments:
            self.departments[dept_id].user_locked = is_locked

    def update_allocation(self, target_id: str, new_percent: float):
        """
        Adjusts target_id to new_percent, redistributing difference among
        available departments.
        """
        if target_id not in self.departments: return
        target = self.departments[target_id]
        
        if target.system_disabled or target.user_locked:
            return

        new_percent = max(0.0, min(1.0, new_percent))
        current_percent = target.percent
        delta = new_percent - current_percent
        
        if math.isclose(delta, 0.0): return

        # Identify 'Liquid' Departments (Available to give/take money)
        liquid_pool = [
            d for d in self.departments.values()
            if d.id != target_id and not d.user_locked and not d.system_disabled
        ]

        if not liquid_pool:
            return # Cannot move if everyone else is locked

        pool_total = sum(d.percent for d in liquid_pool)

        # 1. Check if we are asking for more than the pool has
        if delta > 0 and delta > pool_total:
            # Cap the increase to what's available
            new_percent = current_percent + pool_total
            delta = new_percent - current_percent
        
        # 2. Apply change to target
        target.percent = new_percent
        
        # 3. Redistribute -delta
        remaining_delta = -delta
        
        for dept in liquid_pool:
            if pool_total > 0:
                # Proportional subtraction/addition
                ratio = dept.percent / pool_total
                change = remaining_delta * ratio
            else:
                # Even split if pool was empty (0%)
                change = remaining_delta / len(liquid_pool)
            
            dept.percent = max(0.0, dept.percent + change)
            
        # 4. Final Cleanup (Floating point noise)
        self._normalize_sum()

    def _normalize_sum(self):
        """Ensures total equals 1.0 by adjusting the largest active department."""
        active_depts = [d for d in self.departments.values() if not d.system_disabled]
        if not active_depts: return
        
        total = sum(d.percent for d in active_depts)
        diff = 1.0 - total
        
        if not math.isclose(diff, 0.0):
            # Prefer unlocked departments to absorb diff
            candidates = [d for d in active_depts if not d.user_locked]
            if not candidates:
                candidates = active_depts
                
            # Add dust to largest to minimize visual jump
            best_candidate = max(candidates, key=lambda d: d.percent)
            best_candidate.percent = max(0.0, best_candidate.percent + diff)

    # --- Getters for UI ---

    def get_ui_data(self) -> Dict[str, Any]:
        """Returns complex dict for UI update."""
        allocations = {}
        estimates = {}
        
        # We assume crew works for the WHOLE BLOCK, so total money matters
        total_block_budget = self.budget_per_scene * self.num_scenes
        
        for dept in self.departments.values():
            
            # Budget Amount (Per Scene for display)
            scene_amt = int(self.budget_per_scene * dept.percent)
            
            allocations[dept.id] = {
                "percent": dept.percent,
                "amount": scene_amt,
                "is_user_locked": dept.user_locked,
                "is_system_disabled": dept.system_disabled
            }

            # Estimates (Based on Total Block Budget)
            block_amt = int(total_block_budget * dept.percent)
            
            if dept.system_disabled:
                estimates[dept.id] = "N/A"
            elif block_amt <= 0:
                 estimates[dept.id] = "No Budget"
            else:
                val = self.crew_calculator.calculate_base_efficiency(
                    dept.id, block_amt, total_block_budget, self.visual_style_id
                )
                
                if dept.type == 'crew':
                    # Add variance visual
                    sigma = self.config.crew_skill_sigma * 2
                    min_s = max(1, int(val - sigma))
                    max_s = min(100, int(val + sigma))
                    estimates[dept.id] = f"Skill: {min_s}-{max_s}"
                else:
                    # Resource quality
                    estimates[dept.id] = f"Quality: {int(val)}"
                    
        total_cost = self.get_total_cost()
                    
        return {
            "allocations": allocations,
            "estimates": estimates,
            "total_cost": total_cost,
            "budget_per_scene": self.budget_per_scene
        }

    def get_total_cost(self) -> int:
        total_block_budget = self.budget_per_scene * self.num_scenes
        
        budget_map = {d.id: int(total_block_budget * d.percent) 
                      for d in self.departments.values() 
                      if not d.system_disabled}
        
        return self.cost_calculator.calculate_shooting_bloc_cost(
            self.location_id, budget_map, {}, {}, self.active_policies
        )

    def commit(self, name: str, scheduled_week: int) -> Dict[str, Any]:
        # Generate payload for Controller
        total_block_budget = self.budget_per_scene * self.num_scenes
        allocs = {d.id: d.percent for d in self.departments.values()}
        
        return {
            "name": name,
            "scheduled_absolute_week": scheduled_week,
            "num_scenes": self.num_scenes,
            "logistics": {
                "region_id": self.region_id,
                "location_id": self.location_id,
                "visual_style_id": self.visual_style_id
            },
            "budget_data": {
                "total_budget": total_block_budget,
                "allocations": allocs
            },
            "policies": self.active_policies
        }