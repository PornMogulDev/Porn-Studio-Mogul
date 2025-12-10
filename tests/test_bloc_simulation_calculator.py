import pytest
from unittest.mock import MagicMock

from services.calculation.bloc_simulation_calculator import BlocSimulationCalculator
from data.game_state import ShootingBloc

@pytest.fixture
def mock_data_manager():
    """Provides a mock DataManager."""
    dm = MagicMock()
    dm.picture_set_types.get.return_value = {'momentum_impact': -5.0, 'stress_impact': 10.0}
    dm.production_locations.get.return_value = {
        'simulation_modifiers': {'base_stress': 20.0}
    }
    return dm

@pytest.fixture
def mock_config():
    """Provides a mock ProductionConfig with necessary simulation values."""
    config = MagicMock()
    config.bloc_stress_impact_factor = 0.2
    config.bloc_base_stress = 5.0
    config.momentum_bonus_threshold = 70.0
    config.momentum_bonus_multiplier = 0.8
    config.momentum_penalty_threshold = 30.0
    config.momentum_penalty_multiplier = 1.2
    return config

@pytest.fixture
def calculator(mock_data_manager, mock_config):
    """Provides a BlocSimulationCalculator instance with mock dependencies."""
    return BlocSimulationCalculator(mock_data_manager, mock_config)

def test_calculate_initial_modifiers_low_stress(calculator):
    """
    Tests that a bloc with low stress produces a small, close-to-1.0 stress modifier.
    """
    bloc = MagicMock(spec=ShootingBloc)
    bloc.current_stress = 10.0
    bloc.current_momentum = 50.0
    
    momentum, stress_mod = calculator.calculate_initial_modifiers(bloc)

    assert momentum == 50.0
    # Expected: 1.0 - ((10.0 / 100.0) * 0.2) = 1.0 - 0.02 = 0.98
    assert stress_mod == pytest.approx(0.98)

def test_calculate_initial_modifiers_high_stress(calculator):
    """
    Tests that a bloc with high stress produces a lower, more impactful stress modifier.
    """
    bloc = MagicMock(spec=ShootingBloc)
    bloc.current_stress = 120.0
    bloc.current_momentum = 40.0

    momentum, stress_mod = calculator.calculate_initial_modifiers(bloc)

    assert momentum == 40.0
    # Expected: 1.0 - ((120.0 / 100.0) * 0.2) = 1.0 - 0.24 = 0.76
    assert stress_mod == pytest.approx(0.76)

def test_calculate_post_shoot_deltas_neutral_momentum(calculator):
    """
    Tests delta calculation with neutral momentum, where no bonus or penalty is applied.
    """
    bloc = MagicMock(spec=ShootingBloc)
    bloc.current_momentum = 50.0
    bloc.picture_set_settings = {'type_id': 'test_pics'}
    bloc.set_location_id = 'test_loc'
    bloc.production_cache = {'location_logistics': 75}

    mom_delta, stress_delta = calculator.calculate_post_shoot_deltas(bloc)

    # Momentum delta should only come from the picture set mock value
    assert mom_delta == -5.0
    
    # Stress delta calculation:
    # base_stress (config) = 5.0
    # pic_stress (mock) = 10.0
    # loc_base_stress (mock) = 20.0
    # loc_quality = 75 -> quality_mod = 1.5 - 0.75 = 0.75
    # modified_loc_stress = 20.0 * 0.75 = 15.0
    # Total = 5.0 + 10.0 + 15.0 = 30.0
    # Momentum is neutral, so no multiplier is applied.
    assert stress_delta == pytest.approx(30.0)

def test_calculate_post_shoot_deltas_high_momentum(calculator):
    """
    Tests that high momentum correctly applies a bonus (reduction) to stress gain.
    """
    bloc = MagicMock(spec=ShootingBloc)
    bloc.current_momentum = 80.0  # Above threshold of 70
    bloc.picture_set_settings = {'type_id': 'test_pics'}
    bloc.set_location_id = 'test_loc'
    bloc.production_cache = {'location_logistics': 75}
    
    mom_delta, stress_delta = calculator.calculate_post_shoot_deltas(bloc)
    
    assert mom_delta == -5.0
    
    # Unmodified stress would be 30.0
    # Multiplied by high momentum bonus multiplier: 30.0 * 0.8 = 24.0
    assert stress_delta == pytest.approx(24.0)

def test_calculate_post_shoot_deltas_low_momentum(calculator):
    """
    Tests that low momentum correctly applies a penalty (increase) to stress gain.
    """
    bloc = MagicMock(spec=ShootingBloc)
    bloc.current_momentum = 20.0  # Below threshold of 30
    bloc.picture_set_settings = {'type_id': 'test_pics'}
    bloc.set_location_id = 'test_loc'
    bloc.production_cache = {'location_logistics': 75}
    
    mom_delta, stress_delta = calculator.calculate_post_shoot_deltas(bloc)
    
    assert mom_delta == -5.0
    
    # Unmodified stress would be 30.0
    # Multiplied by low momentum penalty multiplier: 30.0 * 1.2 = 36.0
    assert stress_delta == pytest.approx(36.0)
