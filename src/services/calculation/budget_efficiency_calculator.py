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
        # Map curve names to handler methods to avoid if/elif chains
        self._curve_strategies: Dict[str, Callable[[float, int], float]] = {
            'linear': self._calc_linear,
            'logarithmic': self._calc_logarithmic,
            'step': self._calc_step,
            'exponential': self._calc_exponential
        }

    def calculate_efficiency(self, department_def: Dict, budget: int, total_bloc_budget: int, visual_style_def: Dict) -> float:
        if budget <= 0: return 0.0 # Safety Check
        
        min_budget = department_def.get('min_budget', 0)
        
        # 0. Immediate penalty for under-funding min requirement
        if budget < min_budget:
            return self.config.budget_min_penalty_multiplier

        soft_cap = department_def.get('soft_cap_budget', 1000)
        dept_id = department_def.get('id')
        
        # 1. Calculate Base Efficiency via Curve
        curve_type = department_def.get('curve_type', 'linear')
        calc_method = self._curve_strategies.get(curve_type, self._calc_linear)
        efficiency = calc_method(soft_cap, budget)

        # 2. Apply "Over-production" Penalty for Specific Styles (e.g., Gonzo)
        # If the style heavily penalizes a department, spending WAY over the soft cap hurts quality.
        style_multipliers = visual_style_def.get('department_multipliers', {})
        style_multiplier = style_multipliers.get(dept_id, 1.0)
        
        if style_multiplier < 1.0 and budget > soft_cap:
            # E.g. Verite (0.5 Set Design) -> Spending $5000 on set (Soft Cap $1000)
            # Excess = 4000. Penalty logic applies.
            excess_ratio = (budget - soft_cap) / soft_cap
            # Reduce efficiency based on how much we overspent on something we shouldn't have.
            efficiency -= (excess_ratio * (1.0 - style_multiplier) * self.config.budget_overspend_penalty_factor)

        # 3. Apply Allocation Percentage Mismatch Penalty
        if total_bloc_budget > 0:
            allocation_pct = budget / total_bloc_budget
            targets = visual_style_def.get('allocation_targets', {}).get(dept_id)
            
            if targets:
                penalty_factor = targets.get('penalty_factor', 1.0)
                
                if 'min_percent' in targets and allocation_pct < targets['min_percent']:
                    # Too little % allocated (Cinematic needs 20% Camera, got 10%)
                    shortfall = (targets['min_percent'] - allocation_pct) / targets['min_percent']
                    efficiency *= (1.0 - (shortfall * penalty_factor))
                    
                if 'max_percent' in targets and allocation_pct > targets['max_percent']:
                    # Too much % allocated (Verite needs < 5% Set, got 15%)
                    excess = (allocation_pct - targets['max_percent']) / targets['max_percent']
                    efficiency *= (1.0 - (excess * penalty_factor))

        # 4. Final Multipliers
        global_style_efficiency = visual_style_def.get('budget_efficiency_modifier', 1.0)
        final_score = efficiency * style_multiplier * global_style_efficiency
        
        return max(self.config.budget_efficiency_floor, final_score)

    # --- Curve Strategies ---

    def _calc_linear(self, soft_cap: float, budget: int) -> float:
        if budget <= soft_cap:
            return budget / soft_cap
        # Logarithmic growth past the cap
        excess = budget - soft_cap
        return 1.0 + (math.log(1 + excess) / self.config.linear_curve_divisor)

    def _calc_logarithmic(self, soft_cap: float, budget: int) -> float:
        if budget <= 0: return 0.0
        # Normalized so that soft_cap ~= 1.0
        return math.log(budget) / math.log(soft_cap)

    def _calc_step(self, soft_cap: float, budget: int) -> float:
        ratio = budget / soft_cap
        # Iterate through configured thresholds in ascending order
        # Config example: {0.25: 0.2, 0.5: 0.5, 1.0: 0.8}
        sorted_thresholds = sorted(self.config.step_curve_thresholds.items())
        for threshold, value in sorted_thresholds:
            if ratio < threshold:
                return value
        return 1.0

    def _calc_exponential(self, soft_cap: float, budget: int) -> float:
        ratio = budget / soft_cap
        return ratio ** self.config.exponential_curve_exponent