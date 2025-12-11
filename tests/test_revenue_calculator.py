import pytest
from unittest.mock import MagicMock

# Imports from the project
from services.calculation.revenue_calculator import RevenueCalculator
from services.models.configs import SceneCalculationConfig
from services.models.inputs import RevenueInput, ContentTagInput
from data.game_state import MarketGroupState


@pytest.fixture
def mock_data_manager():
    """Fixture for a mocked DataManager."""
    mock = MagicMock()
    mock.market_data = {
        'viewer_groups': [
            {'name': 'Group A'},
            {'name': 'Group B'}
        ]
    }
    return mock


@pytest.fixture
def scene_calc_config() -> MagicMock:
    """Fixture for a mocked SceneCalculationConfig."""
    mock_config = MagicMock(spec=SceneCalculationConfig)
    mock_config.base_release_revenue = 10000
    mock_config.star_power_revenue_scalar = 0.05
    mock_config.saturation_spend_rate = 0.02
    mock_config.default_sentiment_multiplier = 0.1
    mock_config.revenue_penalties = {
        "short_scene": {"enabled": True, "no_penalty_minutes": 10, "max_penalty_minutes": 2, "max_penalty_multiplier": 0.5},
        "long_monotonous_scene": {"enabled": True, "min_runtime_minutes_for_penalty": 30, "target_concepts_per_10_min": 0.8, "max_penalty_multiplier": 0.7},
        "overstuffed_scene": {"enabled": True, "min_runtime_minutes_for_penalty": 10, "penalty_threshold_tags_per_10_min": 3.0, "max_penalty_tags_per_10_min": 6.0, "max_penalty_multiplier": 0.8}
    }
    return mock_config


@pytest.fixture
def revenue_calculator(mock_data_manager, scene_calc_config) -> RevenueCalculator:
    """Fixture to create a RevenueCalculator instance."""
    return RevenueCalculator(mock_data_manager, scene_calc_config)


@pytest.fixture
def resolved_groups_data() -> dict:
    """Fixture for resolved market group data."""
    return {
        "Group A": {
            "market_share_percent": 60,
            "spending_power": 1.1,
            "focus_bonus": 1.2,
            "preferences": {
                "thematic_sentiments": {"Romantic": 0.1, "Comedy": -0.05},
                "physical_sentiments": {"Athletic": 0.6},
                "action_sentiments": {"Kissing": 0.4},
                "orientation_sentiments": {"Straight": 1.0, "Lesbian": 0.2},
                "dom_sub_sentiments": {"0": 1.0, "1": 1.1},
                "scaling_sentiments": {
                    "Double Penetration": {
                        "based_on_role": "Giver",
                        "applies_after": 1,
                        "bonus_per_unit": 0.15
                    },
                    "Gangbang": {
                        "based_on_role": "Receiver",
                        "penalty_after": 3,
                        "penalty_per_unit": 0.1
                    }
                }
            }
        },
        "Group B": {
            "market_share_percent": 40,
            "spending_power": 0.9,
            "focus_bonus": 1.2,
            "preferences": {
                "thematic_sentiments": {"Dark": 0.2},
                "physical_sentiments": {"Petite": 0.8},
                "action_sentiments": {"Anal": 0.9},
                "orientation_sentiments": {"Straight": 0.5, "Lesbian": 1.0},
                "dom_sub_sentiments": {"0": 1.0},
                "scaling_sentiments": {}
            }
        }
    }


@pytest.fixture
def market_states_data() -> dict:
    """Fixture for market state data."""
    return {
        "Group A": MarketGroupState(name="Group A", current_saturation=0.9, discovered_sentiments={}),
        "Group B": MarketGroupState(name="Group B", current_saturation=1.0, discovered_sentiments={}),
    }

def test_revenue_calculator_init(revenue_calculator, mock_data_manager, scene_calc_config):
    """Test that the calculator initializes correctly."""
    assert revenue_calculator.data_manager == mock_data_manager
    assert revenue_calculator.config == scene_calc_config

def test_baseline_revenue_calculation(revenue_calculator, resolved_groups_data, market_states_data, scene_calc_config):
    """
    Tests a simple revenue calculation for one group with no special bonuses or penalties.
    """
    # ARRANGE
    # Only Group A will have matching preferences
    input_data = RevenueInput(
        title="Test Scene",
        global_tags=["Romantic"],
        content_tags=[
            ContentTagInput(tag_name="Kissing", tag_type="Action", quality=0.8, weight=10, orientation="Straight")
        ],
        star_power_scores={},
        dom_sub_level=0,
        focus_target="",
        total_runtime_minutes=15
    )
    
    # We are only dealing with Group A here for simplicity in manual calculation
    mock_groups = {"Group A": resolved_groups_data["Group A"]}
    mock_states = {"Group A": market_states_data["Group A"]}

    revenue_calculator.data_manager.market_data = {'viewer_groups': [{'name': 'Group A'}]}

    # ACT
    result = revenue_calculator.calculate_revenue(input_data, mock_states, mock_groups)

    # ASSERT
    # Manual calculation for Group A:
    # 1. Thematic Appeal: "Romantic" -> 0.1
    additive_appeal = 0.1
    
    # 2. Content Appeal: "Kissing"
    # total_weight = 10
    # pref for "Kissing" is 0.4
    # quality is 0.8
    # weight is 10, relative weight = 10/10 = 1.0
    # orientation is Straight (1.0)
    # multiplicative_appeal = quality * preference * relative_weight = 0.8 * 0.4 * 1.0 = 0.32
    multiplicative_appeal = 0.32
    
    # 3. Final Interest Score
    # interest = additive + multiplicative = 0.1 + 0.32 = 0.42
    # ds_multiplier (level 0) = 1.0
    # star_power = 1.0
    # focus_bonus = 1.0
    group_interest = 0.42
    
    # 4. Revenue
    # base_revenue = 10000
    # market_share = 0.6
    # spending_power = 1.1
    # saturation = 0.9
    # revenue = (10000 * 0.6) * 0.42 * 1.1 * 0.9 = 6000 * 0.42 * 0.99 = 2494.8
    expected_revenue = 2494

    assert result.total_revenue == expected_revenue
    assert result.viewer_group_interest["Group A"] == round(group_interest, 4)
    assert not result.revenue_modifier_details # No bonuses or penalties
    assert result.market_saturation_updates["Group A"] == pytest.approx(group_interest * scene_calc_config.saturation_spend_rate)

def test_revenue_with_star_power_and_focus_bonus(revenue_calculator, resolved_groups_data, market_states_data):
    """
    Tests that star power and focus target bonuses are correctly applied.
    """
    input_data = RevenueInput(
        title="Test Scene",
        global_tags=["Romantic"],
        content_tags=[ContentTagInput(tag_name="Kissing", tag_type="Action", quality=1.0, weight=10, orientation="Straight")],
        star_power_scores={"Group A": 0.5}, # 50% average popularity for Group A
        dom_sub_level=1,
        focus_target="Group A",
        total_runtime_minutes=20
    )
    mock_groups = {"Group A": resolved_groups_data["Group A"]}
    revenue_calculator.data_manager.market_data = {'viewer_groups': [{'name': 'Group A'}]}
    
    result = revenue_calculator.calculate_revenue(input_data, market_states_data, mock_groups)

    # Interest score before star power/focus:
    # Additive (0.1) + Multiplicative (1.0 * 0.4 * 1.0) = 0.5
    # DS Bonus (level 1): 0.5 * 1.1 = 0.55
    base_interest = 0.55
    
    # Star Power Bonus: 1 + (0.5 * 0.05) = 1.025
    star_power_bonus = 1.025
    
    # Focus Bonus: 1.2
    focus_bonus = 1.2
    
    final_interest = base_interest * star_power_bonus * focus_bonus
    
    assert result.viewer_group_interest["Group A"] == round(final_interest, 4)
    assert "Star Power (Group A)" in result.revenue_modifier_details
    assert result.revenue_modifier_details["Star Power (Group A)"] == 1.02 # Python rounds .5 to nearest even number

def test_short_scene_penalty(revenue_calculator, resolved_groups_data, market_states_data):
    """
    Tests that the short scene penalty is applied correctly.
    """
    input_data = RevenueInput(
        title="Test Scene",
        global_tags=[],
        content_tags=[ContentTagInput(tag_name="Kissing", tag_type="Action", quality=1.0, weight=10, orientation="Straight")],
        star_power_scores={}, dom_sub_level=0, focus_target="",
        total_runtime_minutes=6 # Runtime is between 2 (max penalty) and 10 (no penalty)
    )
    revenue_calculator.data_manager.market_data = {'viewer_groups': [{'name': 'Group A'}]}
    
    result = revenue_calculator.calculate_revenue(input_data, market_states_data, resolved_groups_data)
    
    # Penalty should be interpolated between 0.5 (at 2 mins) and 1.0 (at 10 mins).
    # Runtime of 6 is halfway, so expected multiplier is 0.75
    assert "Short Scene Penalty" in result.revenue_modifier_details
    assert result.revenue_modifier_details["Short Scene Penalty"] == 0.75

def test_monotony_penalty(revenue_calculator, resolved_groups_data, market_states_data):
    """
    Tests that the long, monotonous scene penalty is applied.
    """
    input_data = RevenueInput(
        title="Test Scene",
        global_tags=[],
        content_tags=[
            ContentTagInput(tag_name="Kissing", concept="Intimacy", tag_type="Action", quality=1.0, weight=10),
            ContentTagInput(tag_name="Hugging", concept="Intimacy", tag_type="Action", quality=1.0, weight=10)
        ],
        star_power_scores={}, dom_sub_level=0, focus_target="",
        total_runtime_minutes=40 # Long scene
    )
    revenue_calculator.data_manager.market_data = {'viewer_groups': [{'name': 'Group A'}]}
    
    result = revenue_calculator.calculate_revenue(input_data, market_states_data, resolved_groups_data)

    # 1 unique concept ("Intimacy") in 40 mins -> 1 / 4 = 0.25 concepts per 10 min
    # Target is 0.8. Penalty is interpolated between 0.7 (at 0) and 1.0 (at 0.8)
    # Expected: 0.7 + (0.25 / 0.8) * (1.0 - 0.7) ~= 0.79
    assert "Monotony Penalty" in result.revenue_modifier_details
    assert result.revenue_modifier_details["Monotony Penalty"] == 0.79 # np.interp([0.25], [0, 0.8], [0.7, 1.0])

def test_overstuffed_penalty(revenue_calculator, resolved_groups_data, market_states_data):
    """
    Tests that the overstuffed scene penalty is applied.
    """
    input_data = RevenueInput(
        title="Test Scene",
        global_tags=[],
        content_tags=[
            ContentTagInput(tag_name="C1", concept="C1", tag_type="Action", quality=1.0, weight=10),
            ContentTagInput(tag_name="C2", concept="C2", tag_type="Action", quality=1.0, weight=10),
            ContentTagInput(tag_name="C3", concept="C3", tag_type="Action", quality=1.0, weight=10),
            ContentTagInput(tag_name="C4", concept="C4", tag_type="Action", quality=1.0, weight=10),
            ContentTagInput(tag_name="C5", concept="C5", tag_type="Action", quality=1.0, weight=10),
        ],
        star_power_scores={}, dom_sub_level=0, focus_target="",
        total_runtime_minutes=10 # 5 concepts in 10 minutes
    )
    revenue_calculator.data_manager.market_data = {'viewer_groups': [{'name': 'Group A'}]}
    
    result = revenue_calculator.calculate_revenue(input_data, market_states_data, resolved_groups_data)

    # 5 tags per 10 min. Threshold is 3.0, max density for penalty is 6.0
    # Penalty is interpolated between 1.0 (at 3) and 0.8 (at 6)
    # Expected: 1.0 - ((5-3)/(6-3)) * (1.0-0.8) = 1.0 - (2/3 * 0.2) = 1.0 - 0.1333 = 0.866
    assert "Overstuffed Scene Penalty" in result.revenue_modifier_details
    assert result.revenue_modifier_details["Overstuffed Scene Penalty"] == 0.87 # np.interp([5], [3, 6], [1.0, 0.8])
    
def test_full_calculation_with_multiple_groups(revenue_calculator, resolved_groups_data, market_states_data):
    """
    Tests a full calculation involving two different market groups.
    """
    input_data = RevenueInput(
        title="Test Scene",
        global_tags=["Romantic", "Dark"],
        content_tags=[
            ContentTagInput(tag_name="Athletic", tag_type="Physical", quality=0.9, weight=10),
            ContentTagInput(tag_name="Anal", tag_type="Action", quality=1.0, weight=5, orientation="Lesbian")
        ],
        star_power_scores={"Group A": 0.2, "Group B": 0.8},
        dom_sub_level=0, focus_target="", total_runtime_minutes=25
    )
    
    result = revenue_calculator.calculate_revenue(input_data, market_states_data, resolved_groups_data)

    # Assert that both groups contributed to the revenue
    assert "Group A" in result.viewer_group_interest
    assert "Group B" in result.viewer_group_interest
    assert result.viewer_group_interest["Group A"] > 0
    assert result.viewer_group_interest["Group B"] > 0
    assert result.total_revenue > 0

    # Check that star power was registered for both
    assert "Star Power (Group A)" in result.revenue_modifier_details
    assert "Star Power (Group B)" in result.revenue_modifier_details

    # Check saturation updates for both
    assert "Group A" in result.market_saturation_updates
    assert "Group B" in result.market_saturation_updates

