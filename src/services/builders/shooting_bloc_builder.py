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
    type: str # 'resource' or 'crew'
    user_locked: bool = False
    system_disabled: bool = False
    min_budget: int = 0
    soft_cap: int = 1000 
    curve_type: str = 'linear'
    base_weight: float = 0.0 # Helpful for UI tooltips/weight viz

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
        
        self.region_id: str = "South West (US)"
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
        
        # 1. Add "Location Logistics" (Dynamic Department/Resource)
        # Treated as a resource that outputs a quality score
        self.departments['location_logistics'] = DepartmentState(
            id='location_logistics',
            name='Location & Set',
            basis_points=0,
            type='resource',
            soft_cap=1000,
            min_budget=0,
            curve_type='linear',
            base_weight=0.2 # Implicit weight for location
        )
        
        # 2. Add Standard Resources (Departments)
        if resource_defs:
            for k, v in resource_defs.items():
                all_defs.append((k, v, 'resource'))
        
        # 3. Add Crew (Jobs)
        if crew_defs:
            for k, v in crew_defs.items():
                all_defs.append((k, v, 'crew'))
                
        # Create States
        for dept_id, defs, d_type in all_defs:
            self.departments[dept_id] = DepartmentState(
                id=dept_id,
                name=defs.get('name', dept_id.title()),
                basis_points=0,
                type=d_type,
                min_budget=defs.get('min_budget', 0),
                soft_cap=defs.get('soft_cap_budget', 1000), # Note: Jobs usually don't have soft_cap in JSON yet, handled by calculator defaults or updates
                curve_type=defs.get('curve_type', 'linear'),
                base_weight=defs.get('base_weight', 0.0)
            )
            
        # Initial Even Split
        active_count = len(self.departments)
        if active_count > 0:
            split = self.TOTAL_BPS // active_count
            for d in self.departments.values():
                d.basis_points = split
            
            self._apply_system_constraints()
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
        
        # Update the 'location_logistics' department constraints based on the location def
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

        # Photographer check
        pst_def = self.data_manager.picture_set_types.get(self.picture_set_type_id, {})
        if not pst_def.get('requires_photographer', False):
            to_disable.add('photographer')

        # Camera checks (Jobs)
        if self.camera_mounts[0] == "Tripod": 
            # Note: Depending on design, tripod might still need an operator (Camera A)
            # For this logic, let's assume Camera A is mandatory unless specified otherwise by logic
            pass 
        
        if self.camera_count < 2:
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
                dept.basis_points = 0 # Starts at 0, user must drag or auto-balance
                
        if redistribution_needed:
            self._normalize_sum()

    def toggle_user_lock(self, dept_id: str, is_locked: bool):
        if dept_id in self.departments:
            self.departments[dept_id].user_locked = is_locked

    def update_allocation(self, target_id: str, new_percent: float):
        if target_id not in self.departments: return
        target_bps = int(max(0.0, min(1.0, new_percent)) * self.TOTAL_BPS)
        self._redistribute_bps(target_id, target_bps)

    def _redistribute_bps(self, target_id: str, target_val: int):
        target = self.departments[target_id]
        if target.system_disabled or target.user_locked: return

        current_val = target.basis_points
        delta = target_val - current_val
        if delta == 0: return

        # Identify 'Liquid' Departments (Unlocked, Enabled, Not Target)
        liquid_pool = [
            d for d in self.departments.values()
            if d.id != target_id and not d.user_locked and not d.system_disabled
        ]

        if not liquid_pool: return

        pool_total = sum(d.basis_points for d in liquid_pool)

        # Cap increase to available pool
        if delta > 0 and delta > pool_total:
            target_val = current_val + pool_total
            delta = target_val - current_val
        
        # Apply change
        target.basis_points = target_val
        
        # Distribute remaining delta
        remaining_delta = -delta
        
        if pool_total > 0:
            for dept in liquid_pool:
                ratio = dept.basis_points / pool_total
                share = int(remaining_delta * ratio)
                dept.basis_points = max(0, dept.basis_points + share)
        else:
            # Even split if pool was 0
            share = int(remaining_delta / len(liquid_pool))
            for dept in liquid_pool:
                dept.basis_points += share
            
        self._normalize_sum()

    def _normalize_sum(self):
        """Ensures total equals 10000 by adjusting the largest active unlocked department."""
        active_depts = [d for d in self.departments.values() if not d.system_disabled]
        if not active_depts: return
        
        total = sum(d.basis_points for d in active_depts)
        diff = self.TOTAL_BPS - total
        
        if diff != 0:
            candidates = [d for d in active_depts if not d.user_locked]
            if not candidates:
                candidates = active_depts
            
            # Absorb diff into largest candidate to minimize visual jump
            best_candidate = max(candidates, key=lambda d: d.basis_points)
            new_val = max(0, best_candidate.basis_points + diff)
            best_candidate.basis_points = new_val

    # --- Getters for UI ---

    def get_ui_data(self) -> Dict[str, Any]:
        """
        Returns complex dict for UI update.
        Calculates estimates based on Per-Scene Budget.
        """
        allocations = {}
        estimates = {}
        
        for dept in self.departments.values():
            # UI expects float 0.0-1.0
            percent = dept.basis_points / self.TOTAL_BPS
            
            # Budget Amount (Per Scene)
            scene_amt = int(self.budget_per_scene * percent)
            
            allocations[dept.id] = {
                "percent": percent,
                "amount": scene_amt,
                "is_user_locked": dept.user_locked,
                "is_system_disabled": dept.system_disabled,
                "type": dept.type
            }

            # Estimates
            if dept.system_disabled:
                estimates[dept.id] = "N/A"
            elif scene_amt <= 0:
                 estimates[dept.id] = "No Budget"
            else:
                # Prepare definition dict for calculator
                def_dict = {
                    'id': dept.id,
                    'recommended_budget': dept.soft_cap,
                    'min_budget': dept.min_budget,
                    'curve_type': dept.curve_type
                }
                
                # IMPORTANT: Passing scene_amt and budget_per_scene
                val = self.crew_calculator.calculate_efficiency_raw(
                    def_dict, scene_amt, self.budget_per_scene, self.visual_style_id
                )
                
                if dept.type == 'crew':
                    # Skill Estimate (0-100)
                    base_skill = min(100, val * self.config.crew_skill_baseline_multiplier)
                    sigma = self.config.crew_skill_sigma 
                    min_s = max(1, int(base_skill - sigma))
                    max_s = min(100, int(base_skill + sigma))
                    estimates[dept.id] = f"Skill: {min_s}-{max_s}"
                else:
                    # Resource/Dept Quality Estimate (0-100+)
                    score = int(val * self.config.crew_skill_baseline_multiplier) # Normalizing to same 0-100 scale approximately
                    estimates[dept.id] = f"Quality: {score}"
                    
        total_cost = self.get_total_cost()
                    
        return {
            "allocations": allocations,
            "estimates": estimates,
            "total_cost": total_cost,
            "budget_per_scene": self.budget_per_scene
        }

    def get_total_cost(self) -> int:
        """
        Calculates the upfront cost for the entire bloc.
        """
        # Calculate budgets per scene
        scene_budgets = {}
        for d in self.departments.values():
            if not d.system_disabled:
                scene_budgets[d.id] = int(self.budget_per_scene * (d.basis_points / self.TOTAL_BPS))

        # Scale to Bloc Total (x num_scenes)
        total_department_budgets = {k: v * self.num_scenes for k, v in scene_budgets.items()}
        
        # NOTE: Crew is technically "hired" via this budget in Generic mode.
        # The Cost Calculator sums up department_budgets. 
        # Since we put both Resources and Generic Crew $$ into this map temporarily for calculation,
        # it sums correctly.
        
        return self.cost_calculator.calculate_shooting_bloc_cost(
            self.location_id, 
            total_department_budgets, 
            {}, # No specific crew assignments (Generic/Freelancer cost is covered in dept budgets)
            {}, 
            self.active_policies
        )

    def commit(self, name: str, scheduled_week: int) -> Dict[str, Any]:
        """
        Finalizes the builder state into the dictionary structure expected by SceneCommandService.
        Separates 'resources' into department_budgets and 'crew' into crew_assignments.
        """
        department_budgets = {}
        crew_assignments = {}
        
        for d in self.departments.values():
            if d.system_disabled: continue
            
            # Calculate total budget for this slot for the whole bloc
            per_scene = int(self.budget_per_scene * (d.basis_points / self.TOTAL_BPS))
            total_bloc_amt = per_scene * self.num_scenes
            
            if d.type == 'resource':
                department_budgets[d.id] = total_bloc_amt
            elif d.type == 'crew':
                # Currently only supporting Generic/Freelancer mode via builder
                crew_assignments[d.id] = {
                    "type": "generic",
                    "budget": total_bloc_amt
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
                # We pass the pre-calculated maps
                "department_budgets": department_budgets,
                "crew_assignments": crew_assignments,
                "budget_per_scene": self.budget_per_scene,
                "camera_count": self.camera_count,
                # Total budget is sum of all values
                "total_budget": sum(department_budgets.values()) + sum(c['budget'] for c in crew_assignments.values())
            },
            "policies": self.active_policies
        }