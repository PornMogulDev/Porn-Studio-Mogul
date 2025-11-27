import math
from typing import Dict, Callable
from services.models.configs import ProductionConfig

class BudgetEfficiencyCalculator:
    """
    Calculates the efficiency and quality output of monetary investments 
    into production departments, modulated by the chosen Visual Style.
    """
    def __init__(self, config: ProductionConfig):
        self.config = config
        self._curve_strategies: Dict[str, Callable[[float, int], float]] = {
            'linear': self._calc_linear,
            'logarithmic': self._calc_logarithmic,
            'step': self._calc_step,
            'exponential': self._calc_exponential
        }

    def calculate_efficiency(self, definition: Dict, budget: int, total_bloc_budget: int, visual_style_def: Dict) -> float:
        """
        Calculates efficiency score (typically 0.0 to ~1.5 or 2.0).
        'definition' can be a Department, Job, or Location dictionary.
        """
        # 1. Normalize Keys (Handle Schema Differences)
        # Locations use 'recommended_budget', others use 'soft_cap_budget'
        soft_cap = definition.get('recommended_budget', definition.get('soft_cap_budget', 1000))
        min_budget = definition.get('min_budget', 0)
        dept_id = definition.get('id', 'unknown')
        
        # 2. Base Efficiency via Curve
        curve_type = definition.get('curve_type', 'linear')
        calc_method = self._curve_strategies.get(curve_type, self._calc_linear)
        
        # Guard against zero-cap (which implies no cost needed)
        if soft_cap <= 0:
            return 1.0 if budget >= 0 else 0.0

        efficiency = calc_method(soft_cap, budget)

        # 3. Apply Min Budget Penalty
        # If under min_budget, apply a steep penalty multiplier
        if budget < min_budget:
            efficiency *= self.config.budget_min_penalty_multiplier

        # 4. Apply "Over-production" Penalty for Specific Styles
        # (Only applicable to standard departments/jobs, not usually locations, but logic holds)
        style_multipliers = visual_style_def.get('department_multipliers', {})
        style_multiplier = style_multipliers.get(dept_id, 1.0)
        
        if style_multiplier < 1.0 and budget > soft_cap:
            excess_ratio = (budget - soft_cap) / soft_cap
            # Prevent infinite penalty, cap excess ratio consideration
            excess_ratio = min(excess_ratio, 2.0) 
            efficiency -= (excess_ratio * (1.0 - style_multiplier) * self.config.budget_overspend_penalty_factor)

        # 5. Apply Allocation Percentage Mismatch Penalty
        if total_bloc_budget > 0:
            allocation_pct = budget / total_bloc_budget
            targets = visual_style_def.get('allocation_targets', {}).get(dept_id)
            
            if targets:
                penalty_factor = targets.get('penalty_factor', 1.0)
                
                if 'min_percent' in targets and allocation_pct < targets['min_percent']:
                    shortfall = (targets['min_percent'] - allocation_pct) / targets['min_percent']
                    efficiency *= (1.0 - (shortfall * penalty_factor))
                    
                if 'max_percent' in targets and allocation_pct > targets['max_percent']:
                    excess = (allocation_pct - targets['max_percent']) / targets['max_percent']
                    efficiency *= (1.0 - (excess * penalty_factor))

        # 6. Final Multipliers
        global_style_efficiency = visual_style_def.get('budget_efficiency_modifier', 1.0)
        final_score = efficiency * style_multiplier * global_style_efficiency
        
        return max(self.config.budget_efficiency_floor, final_score)

    # --- Curve Strategies ---

    def _calc_linear(self, soft_cap: float, budget: int) -> float:
        if soft_cap <= 0: return 1.0
        if budget <= soft_cap:
            return budget / soft_cap
        # Diminishing returns after cap
        excess = budget - soft_cap
        return 1.0 + (math.log(1 + excess) / self.config.linear_curve_divisor)

    def _calc_logarithmic(self, soft_cap: float, budget: int) -> float:
        if budget <= 0: return 0.0
        
        # Math Safety: Ensure we don't divide by zero (log(1)=0)
        # and don't take log of <= 0.
        safe_cap = max(1.01, float(soft_cap))
        safe_budget = max(1.0, float(budget))
        
        # Calculate log base (soft_cap) of (budget)
        # Result is 1.0 when budget == soft_cap
        return math.log(safe_budget) / math.log(safe_cap)

    def _calc_step(self, soft_cap: float, budget: int) -> float:
        if soft_cap <= 0: return 1.0
        ratio = budget / soft_cap
        
        # Config thresholds are float ratios (e.g. 0.5) mapped to efficiency (e.g. 0.2)
        # We assume they are sorted
        sorted_thresholds = sorted(self.config.step_curve_thresholds.items())
        
        current_val = 1.0 # Default if above all thresholds (assuming 1.0 is max threshold)
        
        # If budget covers the soft cap, we are at least 1.0
        if ratio >= 1.0:
            return 1.0
            
        for threshold, value in sorted_thresholds:
            if ratio < threshold:
                return value
                
        return 1.0

    def _calc_exponential(self, soft_cap: float, budget: int) -> float:
        if soft_cap <= 0: return 1.0
        ratio = budget / soft_cap
        # Exponential growth usually used for very harsh requirements
        return ratio ** self.config.exponential_curve_exponent