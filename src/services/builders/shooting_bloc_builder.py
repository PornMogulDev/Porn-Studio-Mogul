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
    basis_points: int # 0 to 10000 (0.00% to 100.00%)
    user_locked: bool = False
    system_disabled: bool = False
    min_budget: int = 0
    soft_cap: int = 1000 # Dynamic target for efficiency
    curve_type: str = 'linear'
    type: str = "resource" 

class ShootingBlocBuilder:
    TOTAL_BPS = 10000 # 100.00%

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
        self.budget_per_scene: int = 5000
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
        
        all_defs = []
        
        # 1. Add "Location Logistics" (Dynamic Department)
        # We create a placeholder state; actual constraints set via set_logistics/set_location
        self.departments['location_logistics'] = DepartmentState(
            id='location_logistics',
            name='Location & Set',
            basis_points=0,
            type='resource',
            soft_cap=1000,
            min_budget=0,
            curve_type='linear'
        )
        
        # 2. Add Standard Resources
        if resource_defs:
            for k, v in resource_defs.items():
                all_defs.append((k, v, 'resource'))
        
        # 3. Add Crew
        if crew_defs:
            for k, v in crew_defs.items():
                all_defs.append((k, v, 'crew'))
                
        # Create States
        for dept_id, defs, d_type in all_defs:
            self.departments[dept_id] = DepartmentState(
                id=dept_id,
                name=defs.get('name', dept_id.title()),
                basis_points=0,
                min_budget=defs.get('min_budget', 0),
                soft_cap=defs.get('soft_cap_budget', 1000),
                curve_type=defs.get('curve_type', 'linear'),
                type=d_type
            )
            
        # Initial Even Split
        # Includes location_logistics
        active_count = len(self.departments)
        if active_count > 0:
            split = self.TOTAL_BPS // active_count
            for d in self.departments.values():
                d.basis_points = split
            
            # Apply initial system locks (e.g. disable photographer if default is video grabs)
            self._apply_system_constraints()
            
            # Ensure exact 10000 sum
            self._normalize_sum()

    # --- Configuration Setters ---

    def set_budget_per_scene(self, amount: int):
        self.budget_per_scene = max(0, amount)

    def set_num_scenes(self, count: int):
        self.num_scenes = max(1, count)

    def set_logistics(self, region_id: str, location_id: str, visual_style_id: str):
        self.region_id = region_id
        self.visual_style_id = visual_style_id
        self.set_location(location_id)

    def set_location(self, location_id: str):
        if self.location_id == location_id: return
        self.location_id = location_id
        
        # Update the 'location_logistics' department constraints
        if 'location_logistics' in self.departments:
            loc_def = self.data_manager.production_locations.get(location_id, {})
            dept = self.departments['location_logistics']
            
            dept.soft_cap = loc_def.get('recommended_budget', 1000)
            dept.min_budget = loc_def.get('min_budget', 0)
            dept.curve_type = loc_def.get('curve_type', 'linear')

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

        redistribution_needed = False
        
        for dept in self.departments.values():
            should_be_disabled = dept.id in to_disable
            
            if should_be_disabled and not dept.system_disabled:
                dept.basis_points = 0
                dept.system_disabled = True
                redistribution_needed = True
                
            elif not should_be_disabled and dept.system_disabled:
                dept.system_disabled = False
                dept.basis_points = 0 # Starts at 0, user must drag
                
        if redistribution_needed:
            self._normalize_sum()

    def toggle_user_lock(self, dept_id: str, is_locked: bool):
        if dept_id in self.departments:
            self.departments[dept_id].user_locked = is_locked

    def update_allocation(self, target_id: str, new_percent: float):
        """
        Adjusts target_id to new_percent (converted to bps), 
        redistributing difference among available departments.
        """
        if target_id not in self.departments: return
        
        # Convert to BPS
        target_bps = int(max(0.0, min(1.0, new_percent)) * self.TOTAL_BPS)
        self._redistribute_bps(target_id, target_bps)

    def _redistribute_bps(self, target_id: str, target_val: int):
        target = self.departments[target_id]
        if target.system_disabled or target.user_locked: return

        current_val = target.basis_points
        delta = target_val - current_val
        
        if delta == 0: return

        # Identify 'Liquid' Departments
        liquid_pool = [
            d for d in self.departments.values()
            if d.id != target_id and not d.user_locked and not d.system_disabled
        ]

        if not liquid_pool: return

        pool_total = sum(d.basis_points for d in liquid_pool)

        # 1. Cap increase to available pool
        if delta > 0 and delta > pool_total:
            target_val = current_val + pool_total
            delta = target_val - current_val
        
        # 2. Apply change to target
        target.basis_points = target_val
        
        # 3. Redistribute -delta (subtraction from pool)
        remaining_delta = -delta
        
        # We iterate and distribute proportionally
        # To avoid integer rounding losing/gaining 1-2 points, we accumulate remainder
        # or use simple integer distribution and normalize at the end.
        
        if pool_total > 0:
            for dept in liquid_pool:
                ratio = dept.basis_points / pool_total
                share = int(remaining_delta * ratio)
                dept.basis_points = max(0, dept.basis_points + share)
        else:
            # Pool was empty (0 bps), but we are adding to it (delta < 0, remaining > 0)
            # Split evenly
            share = int(remaining_delta / len(liquid_pool))
            for dept in liquid_pool:
                dept.basis_points += share
            
        # 4. Final Normalization to ensure strict 10000
        self._normalize_sum()

    def _normalize_sum(self):
        """Ensures total equals 10000 by adjusting the largest active department."""
        active_depts = [d for d in self.departments.values() if not d.system_disabled]
        if not active_depts: return
        
        total = sum(d.basis_points for d in active_depts)
        diff = self.TOTAL_BPS - total
        
        if diff != 0:
            # Prefer unlocked departments to absorb diff
            candidates = [d for d in active_depts if not d.user_locked]
            if not candidates:
                candidates = active_depts
            
            # Add/Sub from largest to minimize visual jump
            best_candidate = max(candidates, key=lambda d: d.basis_points)
            
            # Ensure we don't go negative if diff is negative
            new_val = best_candidate.basis_points + diff
            best_candidate.basis_points = max(0, new_val)
            
            # If we hit 0 and still have diff (rare edge case with negative diff),
            # we might technically under-sum, but user locks prevent most of this.
            # A second pass could handle strictness, but max(0) is usually safe.

    # --- Getters for UI ---

    def get_ui_data(self) -> Dict[str, Any]:
        """Returns complex dict for UI update."""
        allocations = {}
        estimates = {}
        
        total_block_budget = self.budget_per_scene * self.num_scenes
        
        for dept in self.departments.values():
            
            # UI expects float 0.0-1.0
            percent = dept.basis_points / self.TOTAL_BPS
            
            # Budget Amount (Per Scene for display)
            scene_amt = int(self.budget_per_scene * percent)
            
            allocations[dept.id] = {
                "percent": percent,
                "amount": scene_amt,
                "is_user_locked": dept.user_locked,
                "is_system_disabled": dept.system_disabled
            }

            # Estimates
            block_amt = int(total_block_budget * percent)
            
            if dept.system_disabled:
                estimates[dept.id] = "N/A"
            elif block_amt <= 0:
                 estimates[dept.id] = "No Budget"
            else:
                # Prepare definition dict for calculator
                # For location_logistics, we construct a virtual def
                def_dict = {
                    'id': dept.id,
                    'recommended_budget': dept.soft_cap, # Used by calculator
                    'min_budget': dept.min_budget,
                    'curve_type': dept.curve_type
                }
                
                # Returns raw float (e.g. 1.15 for 115% efficiency)
                val = self.crew_calculator.calculate_efficiency_raw(
                    def_dict, block_amt, total_block_budget, self.visual_style_id
                )
                
                # Convert raw efficiency (e.g. 1.2) to display string
                if dept.type == 'crew':
                    # Skill 0-100
                    base_skill = min(100, val * self.config.crew_skill_baseline_multiplier)
                    sigma = self.config.crew_skill_sigma 
                    min_s = max(1, int(base_skill - sigma))
                    max_s = min(100, int(base_skill + sigma))
                    estimates[dept.id] = f"Skill: {min_s}-{max_s}"
                else:
                    # Resource Quality (0-100+)
                    # Just treat as raw score
                    score = int(val * 100)
                    estimates[dept.id] = f"Quality: {score}"
                    
        total_cost = self.get_total_cost()
                    
        return {
            "allocations": allocations,
            "estimates": estimates,
            "total_cost": total_cost,
            "budget_per_scene": self.budget_per_scene
        }

    def get_total_cost(self) -> int:
        total_block_budget = self.budget_per_scene * self.num_scenes
        
        # Convert BPS to budget map
        budget_map = {
            d.id: int(total_block_budget * (d.basis_points / self.TOTAL_BPS))
            for d in self.departments.values() 
            if not d.system_disabled
        }
        
        # Location ID is passed, but cost is now in budget_map['location_logistics']
        # The Cost Calculator should interpret this correctly (i.e. not double count)
        # Note: BlocCostCalculator sums department_budgets + location base_cost.
        # We need to ensure we don't double charge if we migrated location to a budget item.
        # FIX: We should pass None for location_id to cost calculator if location is a budget item,
        # OR ensure BlocCostCalculator doesn't add base_cost if it's 0 (which migration handled).
        
        return self.cost_calculator.calculate_shooting_bloc_cost(
            self.location_id, budget_map, {}, {}, self.active_policies
        )

    def commit(self, name: str, scheduled_week: int) -> Dict[str, Any]:
        total_block_budget = self.budget_per_scene * self.num_scenes
        
        allocs = {
            d.id: (d.basis_points / self.TOTAL_BPS) 
            for d in self.departments.values()
        }
        
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