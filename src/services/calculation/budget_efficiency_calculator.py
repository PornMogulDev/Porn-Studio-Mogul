import math
from typing import Dict, Callable
from services.models.configs import ProductionConfig

class BudgetEfficiencyCalculator:
    """
    Calculates the efficiency of monetary investments into production departments.

    This class translates a budget amount into an "efficiency score" (typically a
    multiplier around 1.0), which is then used by other calculators to determine
    final production quality or crew skill. The calculation is modulated by the
    department's defined budget curve and penalties/bonuses from the chosen
    Visual Style.
    """
    def __init__(self, config: ProductionConfig):
        self.config = config
        self._curve_strategies: Dict[str, Callable[[float, int], float]] = {
            'linear': self._calc_linear_with_diminishing_returns,
            'logarithmic': self._calc_logarithmic,
            'step': self._calc_step,
            'exponential': self._calc_exponential
        }

    def calculate_efficiency(self, definition: Dict, budget: int, total_bloc_budget: int, visual_style_def: Dict) -> float:
        """
        Calculates a final efficiency score (typically 0.0 to ~2.0).

        The process is a pipeline of modifications:
        1. Calculate a base efficiency from a budget curve (linear, log, etc.).
        2. Apply a penalty if the budget is below the defined minimum.
        3. Apply a penalty for overspending on departments that a Visual Style de-emphasizes.
        4. Apply a penalty if the department's budget allocation percentage misaligns
           with the Visual Style's recommended targets.
        5. Apply final global and department-specific multipliers from the Visual Style.

        Args:
            definition: The definition dictionary for a Department, Job, or Location.
            budget: The per-scene budget allocated to this item.
            total_bloc_budget: The total per-scene budget for the entire bloc, for context.
            visual_style_def: The definition dictionary for the chosen Visual Style.

        Returns:
            The final calculated efficiency score as a float.
        """
        # 1. Normalize Keys from definition (handles differences between locations, jobs, etc.)
        soft_cap = definition.get('recommended_budget', definition.get('soft_cap_budget', 1000))
        min_budget = definition.get('min_budget', 0)
        dept_id = definition.get('id', 'unknown')
        
        # 2. Base Efficiency via Curve Strategy
        curve_type = definition.get('curve_type', 'linear')
        calc_method = self._curve_strategies.get(curve_type, self._calc_linear_with_diminishing_returns)
        
        # If a department has no cost (soft_cap <= 0), its efficiency is always 1.0.
        if soft_cap <= 0:
            return 1.0 if budget >= 0 else 0.0

        efficiency = calc_method(soft_cap, budget)

        # 3. Apply Minimum Budget Penalty
        # If under the minimum required budget, apply a steep penalty.
        if budget < min_budget:
            efficiency *= self.config.budget_min_penalty_multiplier

        # 4. Apply "Over-production" Penalty for Specific Styles
        # This penalizes spending *more* than the soft cap on a department that the
        # visual style explicitly discourages (e.g., high-end 'Costumes' for a 'Gritty' style).
        style_multipliers = visual_style_def.get('department_multipliers', {})
        style_multiplier = style_multipliers.get(dept_id, 1.0)
        
        if style_multiplier < 1.0 and budget > soft_cap:
            # Calculate how much was overspent relative to the cap.
            excess_ratio = (budget - soft_cap) / soft_cap
            # The penalty is proportional to the amount of overspending.
            # Cap excess_ratio to prevent extreme/infinite penalties.
            excess_ratio = min(excess_ratio, 2.0) 
            penalty = (excess_ratio * (1.0 - style_multiplier) * self.config.budget_overspend_penalty_factor)
            efficiency -= penalty

        # 5. Apply Allocation Percentage Mismatch Penalty
        # This penalizes the efficiency if the department's share of the total budget
        # is outside the optimal range defined by the Visual Style.
        if total_bloc_budget > 0:
            allocation_pct = budget / total_bloc_budget
            targets = visual_style_def.get('allocation_targets', {}).get(dept_id)
            
            if targets:
                penalty_factor = targets.get('penalty_factor', 1.0)
                
                # Penalize for being under the minimum required percentage.
                if 'min_percent' in targets and allocation_pct < targets['min_percent']:
                    # Calculate the shortfall as a percentage of the minimum.
                    shortfall = (targets['min_percent'] - allocation_pct) / targets['min_percent']
                    efficiency *= (1.0 - (shortfall * penalty_factor))
                    
                # Penalize for being over the maximum recommended percentage.
                if 'max_percent' in targets and allocation_pct > targets['max_percent']:
                    excess = (allocation_pct - targets['max_percent']) / targets['max_percent']
                    efficiency *= (1.0 - (excess * penalty_factor))

        # 6. Apply Final Multipliers from Visual Style
        global_style_efficiency = visual_style_def.get('budget_efficiency_modifier', 1.0)
        final_score = efficiency * style_multiplier * global_style_efficiency
        
        # Clamp to a final floor to prevent negative or absurdly low values.
        return max(self.config.budget_efficiency_floor, final_score)

    # --- Curve Strategies ---

    def _get_bonus_from_excess_budget(self, soft_cap: float, budget: int) -> float:
        """
        Calculates a bonus efficiency score for budgets that exceed the soft cap.
        Uses a power curve for more predictable, but still diminishing, returns.
        An exponent of 0.6 is more generous than 0.75.
        """
        excess_ratio = (budget - soft_cap) / soft_cap
        bonus = excess_ratio ** 0.6
        return bonus / self.config.linear_curve_divisor

    def _calc_linear_with_diminishing_returns(self, soft_cap: float, budget: int) -> float:
        """
        A linear growth curve up to the soft cap, with diminishing returns beyond it.
        - Below cap: Efficiency grows 1:1 with budget (budget / soft_cap).
        - At cap: Efficiency is 1.0.
        - Above cap: Efficiency is 1.0 + a bonus from the excess budget.
        """
        if soft_cap <= 0: return 1.0
        if budget <= soft_cap:
            return budget / soft_cap
        
        bonus = self._get_bonus_from_excess_budget(soft_cap, budget)
        return 1.0 + bonus

    def _calc_logarithmic(self, soft_cap: float, budget: int) -> float:
        """
        A logarithmic growth curve, reaching ~1.0 efficiency at the soft cap.
        Gains are front-loaded. Budgets over the cap provide a smaller bonus.
        """
        if budget <= 0: return 0.0
        
        # Original logarithmic growth for budgets up to the soft cap.
        if budget <= soft_cap:
            safe_cap = max(1.01, float(soft_cap))
            safe_budget = max(1.0, float(budget))
            # Calculate log base (soft_cap) of (budget)
            # Result is ~1.0 when budget is near soft_cap
            return math.log(safe_budget) / math.log(safe_cap)

        # For budgets over the cap, start at 1.0 and add the standard bonus.
        bonus = self._get_bonus_from_excess_budget(soft_cap, budget)
        return 1.0 + bonus


    def _calc_step(self, soft_cap: float, budget: int) -> float:
        """
        A step function where efficiency jumps at configured budget thresholds.
        Reaching the soft cap grants 1.0 efficiency, with bonuses for exceeding it.
        """
        if soft_cap <= 0: return 1.0
        ratio = budget / soft_cap
        
        if ratio >= 1.0:
            bonus = self._get_bonus_from_excess_budget(soft_cap, budget)
            return 1.0 + bonus
            
        # Config thresholds are float ratios (e.g. 0.5) mapped to efficiency (e.g. 0.2)
        sorted_thresholds = sorted(self.config.step_curve_thresholds.items())
        
        # Find the highest threshold this budget meets
        current_value = 0.0
        for threshold, value in sorted_thresholds:
            if ratio >= threshold:
                current_value = value
            else:
                break # Ratios are sorted, no need to check further
        return current_value


    def _calc_exponential(self, soft_cap: float, budget: int) -> float:
        """
        An exponential growth curve.
        Efficiency grows slowly and then rapidly accelerates as budget approaches the cap.
        """
        if soft_cap <= 0: return 1.0
        ratio = budget / soft_cap
        # Exponential growth usually used for very harsh requirements
        return ratio ** self.config.exponential_curve_exponent