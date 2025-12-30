
import pytest
from typing import Dict

from data.data_manager import DataManager
from services.calculation.budget_efficiency_calculator import BudgetEfficiencyCalculator
from services.models.configs import ProductionConfig


@pytest.fixture
def game_data_manager() -> DataManager:
    """Fixture to provide a DataManager instance."""
    return DataManager()


@pytest.fixture
def mock_production_config() -> ProductionConfig:
    """Fixture to create a mock ProductionConfig for testing."""
    return ProductionConfig(
        budget_min_penalty_multiplier=0.5,
        budget_overspend_penalty_factor=0.5,
        budget_efficiency_floor=0.1,
        linear_curve_divisor=10.0,
        exponential_curve_exponent=2.0,
        step_curve_thresholds={0.25: 0.2, 0.5: 0.5, 0.75: 0.8},
        crew_skill_baseline_multiplier=60,
        crew_skill_sigma=5,
        bloc_base_momentum=0.0,
        bloc_base_stress=0.0,
        bloc_stress_impact_factor=0.0,
        momentum_bonus_threshold=0.0,
        momentum_bonus_multiplier=0.0,
        momentum_penalty_threshold=0.0,
        momentum_penalty_multiplier=0.0
    )


@pytest.fixture
def budget_calculator(mock_production_config: ProductionConfig) -> BudgetEfficiencyCalculator:
    """Fixture to provide a BudgetEfficiencyCalculator instance."""
    return BudgetEfficiencyCalculator(config=mock_production_config)


def get_department_efficiency(
    budget_calc: BudgetEfficiencyCalculator,
    data_manager: DataManager,
    dept_id: str,
    budget: int,
    total_budget: int,
    visual_style_id: str = "standard"
) -> float:
    """Helper to calculate a department's raw budget efficiency."""
    dept_def = data_manager.production_departments.get(dept_id)
    style_def = data_manager.visual_styles.get(visual_style_id, {})

    if not dept_def:
        pytest.fail(f"Department definition for '{dept_id}' not found.")

    return budget_calc.calculate_efficiency(dept_def, budget, total_budget, style_def)


def test_logarithmic_curve_growth(budget_calculator: BudgetEfficiencyCalculator, game_data_manager: DataManager):
    """
    Tests if the logarithmic curve's efficiency value continues to grow.
    """
    dept_id = "camera_equipment"  # Uses logarithmic curve

    budget_at_cap = 5000
    budget_high = 100000
    budget_very_high = 1000000

    eff_at_cap = get_department_efficiency(budget_calculator, game_data_manager, dept_id, budget_at_cap, budget_at_cap)
    eff_high = get_department_efficiency(budget_calculator, game_data_manager, dept_id, budget_high, budget_high)
    eff_very_high = get_department_efficiency(budget_calculator, game_data_manager, dept_id, budget_very_high, budget_very_high)

    print(f"Efficiencies for '{dept_id}': Cap={eff_at_cap:.2f}, High={eff_high:.2f}, Very High={eff_very_high:.2f}")

    assert eff_at_cap == pytest.approx(1.0, abs=0.1)
    assert eff_high > eff_at_cap
    assert eff_very_high > eff_high


def test_linear_curve_growth(budget_calculator: BudgetEfficiencyCalculator, game_data_manager: DataManager):
    """
    Tests if the linear curve's efficiency value continues to grow.
    """
    dept_id = "set_design"  # Uses linear curve, soft cap 4000

    budget_at_cap = 4000
    budget_high = 80000  # 20x cap
    budget_very_high = 800000  # 200x cap

    eff_at_cap = get_department_efficiency(budget_calculator, game_data_manager, dept_id, budget_at_cap, budget_at_cap)
    eff_high = get_department_efficiency(budget_calculator, game_data_manager, dept_id, budget_high, budget_high)
    eff_very_high = get_department_efficiency(budget_calculator, game_data_manager, dept_id, budget_very_high,
                                            budget_very_high)

    print(f"Efficiencies for '{dept_id}': Cap={eff_at_cap:.2f}, High={eff_high:.2f}, Very High={eff_very_high:.2f}")

    assert eff_at_cap == pytest.approx(1.0, abs=0.1)
    assert eff_high > eff_at_cap
    assert eff_very_high > eff_high


def test_step_curve_growth(budget_calculator: BudgetEfficiencyCalculator, game_data_manager: DataManager):
    """
    Tests the step curve to ensure it grows past the soft cap.
    """
    dept_id = "craft_services"  # Uses step curve, soft cap 1000

    budget_below_step = 700
    budget_above_step = 800
    budget_at_cap = 1000
    budget_above_cap = 2000

    eff_below = get_department_efficiency(budget_calculator, game_data_manager, dept_id, budget_below_step,
                                            budget_below_step)
    eff_above = get_department_efficiency(budget_calculator, game_data_manager, dept_id, budget_above_step,
                                            budget_above_step)
    eff_at_cap = get_department_efficiency(budget_calculator, game_data_manager, dept_id, budget_at_cap, budget_at_cap)
    eff_way_above = get_department_efficiency(budget_calculator, game_data_manager, dept_id, budget_above_cap,
                                                budget_above_cap)

    print(
        f"Efficiencies for '{dept_id}': Below={eff_below:.2f}, Above={eff_above:.2f}, Cap={eff_at_cap:.2f}, Way Above={eff_way_above:.2f}")

    # Check that crossing a step increases efficiency
    assert eff_above > eff_below
    # Check that reaching the cap increases efficiency
    assert eff_at_cap > eff_above
    # Check that exceeding the cap continues to increase efficiency
    assert eff_way_above > eff_at_cap
