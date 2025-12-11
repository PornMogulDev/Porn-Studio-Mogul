import pytest
from unittest.mock import MagicMock, call
import math

from services.calculation.shoot_results_calculator import ShootResultsCalculator
from services.models.configs import SceneCalculationConfig
from services.models.results import TalentShootOutcome, FatigueResult
from data.game_state import Scene, Talent, VirtualPerformer, ActionSegment, SlotAssignment
from database.db_models import TalentDB # for Union type hint


@pytest.fixture
def mock_data_manager():
    """Fixture for a mocked DataManager with tag definitions."""
    mock = MagicMock()
    mock.tag_definitions = {
        "tag_A": {"type": "Action", "stamina_modifier": 1.0},
        "tag_B": {"type": "Action", "stamina_modifier": 0.5},
        "tag_C": {"type": "Action", "stamina_modifier": 2.0},
    }
    return mock

@pytest.fixture
def mock_scene_calc_config():
    """Fixture for a mocked SceneCalculationConfig."""
    mock_config = MagicMock(spec=SceneCalculationConfig)
    mock_config.stamina_to_pool_multiplier = 10.0
    mock_config.max_stress_threshold = 100.0
    mock_config.burnout_conversion_rate = 0.1
    mock_config.skill_gain_base_rate = 0.01
    mock_config.skill_gain_curve_steepness = 2.0
    mock_config.ds_skill_gain_base_rate = 0.005
    mock_config.ds_skill_gain_disposition_multiplier = 1.2
    mock_config.ds_skill_gain_dynamic_level_multipliers = {1: 0.8, 2: 1.0, 3: 1.2}
    mock_config.exp_gain_base_rate = 0.02
    mock_config.exp_gain_curve_steepness = 1.5
    mock_config.maximum_skill_level = 100.0
    return mock_config

@pytest.fixture
def mock_role_performance_calculator():
    """Fixture for a mocked RolePerformanceCalculator."""
    mock = MagicMock()
    # Default behavior: returns 1.0 for stamina modifier
    mock.get_role_stamina_modifier.return_value = 1.0 
    return mock

@pytest.fixture
def mock_stress_calculator():
    """Fixture for a mocked StressCalculator."""
    mock = MagicMock()
    # Default behavior: returns a fixed stress gain
    mock.calculate_stress_gain.return_value = 10.0 
    return mock

@pytest.fixture
def shoot_results_calculator(mock_data_manager, mock_scene_calc_config,
                             mock_role_performance_calculator, mock_stress_calculator):
    """Fixture for a ShootResultsCalculator instance."""
    return ShootResultsCalculator(
        mock_data_manager, mock_scene_calc_config,
        mock_role_performance_calculator, mock_stress_calculator
    )

# --- Test Data Fixtures ---
@pytest.fixture
def talent_data():
    """Returns a basic Talent instance."""
    return Talent(
        id=1, alias="Test Talent", age=25, gender="Female", nationality="US",
        primary_ethnicity="Caucasian", performance=50.0, acting=50.0,
        stamina=50.0, dom_skill=50.0, sub_skill=50.0, ambition=50, traits=[],
        ds_dynamic_preferences={}, professionalism=5, orientation_score=0,
        disposition_score=0, experience=50.0, stress=0.0
    )

@pytest.fixture
def scene_data():
    """Returns a basic Scene instance."""
    scene = Scene(
        id=1, title="Test Scene", status="scheduled", focus_target="",
        scheduled_absolute_week=1, location="Studio",
        total_runtime_minutes=20,
        virtual_performers=[
            VirtualPerformer(id=101, name="VP A", gender="Female", disposition="Sub"),
            VirtualPerformer(id=102, name="VP B", gender="Male", disposition="Dom")
        ],
        final_cast={"101": 1, "102": 2}, # VP 101 -> Talent 1, VP 102 -> Talent 2
        action_segments=[
            ActionSegment(tag_name="tag_A", runtime_percentage=50,
                          slot_assignments=[SlotAssignment(slot_id="tag_A_role_1", virtual_performer_id=101)]),
            ActionSegment(tag_name="tag_B", runtime_percentage=50,
                          slot_assignments=[SlotAssignment(slot_id="tag_B_role_1", virtual_performer_id=101)])
        ]
    )
    # Mock expanded action segments for simplicity in testing _calculate_stamina_cost_for_role
    scene.get_expanded_action_segments = MagicMock(return_value=[
        ActionSegment(tag_name="tag_A", runtime_percentage=50,
                      slot_assignments=[SlotAssignment(slot_id="tag_A_role_1", virtual_performer_id=101)]),
        ActionSegment(tag_name="tag_B", runtime_percentage=50,
                      slot_assignments=[SlotAssignment(slot_id="tag_B_role_1", virtual_performer_id=101)])
    ])
    return scene

@pytest.fixture
def bloc_context_data():
    """Returns a basic bloc_context dictionary."""
    return {
        "location_def": {},
        "craft_services_efficiency": 1.0,
        "health_safety_score": 50,
        "crew_assignments": {},
    }


class TestCalculateTalentOutcomes:
    """Tests for the calculate_talent_outcomes method."""

    def test_basic_outcome_calculation(self, shoot_results_calculator, talent_data, scene_data, bloc_context_data, mock_scene_calc_config):
        """
        Tests calculation of fatigue, skills, and stress for a single talent
        with a simple scene.
        """
        # ARRANGE
        talent = talent_data
        talent.stamina = 5.0 # Lower stamina to ensure some fatigue gain
        talent.id = 1
        scene_data.final_cast = {"101": 1} # Only Talent 1 in cast

        # Mock the `_calculate_fatigue` and other private methods if too complex
        # For this test, we'll let them run and check the aggregate outcome.

        # Expected stamina cost for VP 101:
        # tag_A runtime = 20 * 0.5 = 10
        # tag_B runtime = 20 * 0.5 = 10
        # Total stamina cost = 10 * 1.0 (modifier) + 10 * 1.0 (modifier) = 20.0
        expected_stamina_cost = 20.0

        # Fatigue:
        # max_stamina = 5.0 (talent.stamina) * 10.0 (multiplier) = 50.0
        # overdraw_ratio = (20.0 - 50.0) / 50.0 = -0.6 (no overdraw) -> 0 fatigue
        # This is where I realize my expected fatigue gain is wrong for this setup.
        # Let's adjust talent.stamina for some fatigue:
        talent.stamina = 1.0 # max_stamina = 10.0
        # overdraw_ratio = (20.0 - 10.0) / 10.0 = 1.0
        expected_fatigue_gain = 100 # min(100, int(1.0 * 100))

        # Skill Gains:
        # p_gain = (20 * 0.01) * (1 - (50/100)**2) = 0.2 * (1 - 0.25) = 0.2 * 0.75 = 0.15
        expected_p_gain = mock_scene_calc_config.skill_gain_base_rate * scene_data.total_runtime_minutes * (1 - (talent.performance / 100)**mock_scene_calc_config.skill_gain_curve_steepness)
        expected_a_gain = mock_scene_calc_config.skill_gain_base_rate * scene_data.total_runtime_minutes * (1 - (talent.acting / 100)**mock_scene_calc_config.skill_gain_curve_steepness)
        expected_s_gain = mock_scene_calc_config.skill_gain_base_rate * scene_data.total_runtime_minutes * (1 - (talent.stamina / 100)**mock_scene_calc_config.skill_gain_curve_steepness)

        # DS Skill Gain (Talent disposition Sub, Scene dynamic level 0):
        # Should be 0, as dom_sub_dynamic_level is 0 in scene_data fixture
        expected_dom_gain, expected_sub_gain = 0.0, 0.0

        # Experience Gain:
        # exp_gain = (20 * 0.02) * (1 - (50/100)**1.5) = 0.4 * (1 - 0.35355) = 0.4 * 0.64645 = 0.25858
        expected_exp_gain = mock_scene_calc_config.exp_gain_base_rate * scene_data.total_runtime_minutes * (1 - (talent.experience / 100)**mock_scene_calc_config.exp_gain_curve_steepness)

        # Stress Gain: mocked to 10.0
        expected_stress_gain = 10.0

        # Burnout Gain: talent.stress is 0.0, projected_total_stress = 0.0 + 10.0 = 10.0.
        # This is < max_stress_threshold (100.0), so burnout_gain should be 0.
        expected_burnout_gain = 0.0

        # ACT
        outcomes = shoot_results_calculator.calculate_talent_outcomes(
            scene_data, [talent], [], bloc_context_data
        )

        # ASSERT
        assert len(outcomes) == 1
        outcome = outcomes[0]
        assert outcome.talent_id == talent.id
        assert outcome.stamina_cost == expected_stamina_cost
        assert outcome.fatigue_result.new_fatigue_level == (talent.fatigue + expected_fatigue_gain)
        assert outcome.skill_gains['performance'] == pytest.approx(expected_p_gain)
        assert outcome.skill_gains['acting'] == pytest.approx(expected_a_gain)
        assert outcome.skill_gains['stamina'] == pytest.approx(expected_s_gain)
        assert outcome.skill_gains['dom_skill'] == pytest.approx(expected_dom_gain)
        assert outcome.skill_gains['sub_skill'] == pytest.approx(expected_sub_gain)
        assert outcome.experience_gain == pytest.approx(expected_exp_gain)
        assert outcome.stress_gain == expected_stress_gain
        assert outcome.burnout_gain == expected_burnout_gain

    def test_burnout_gain_calculation(self, shoot_results_calculator, talent_data, scene_data, bloc_context_data, mock_scene_calc_config, mock_stress_calculator):
        """
        Tests that burnout is correctly calculated when stress exceeds threshold.
        """
        # ARRANGE
        talent = talent_data
        talent.stress = 95.0 # High existing stress
        talent.id = 1
        scene_data.final_cast = {"101": 1}

        mock_stress_calculator.calculate_stress_gain.return_value = 10.0 # Adds 10 stress

        # Projected total stress = 95.0 + 10.0 = 105.0
        # max_stress_threshold = 100.0
        # excess_stress = 105.0 - 100.0 = 5.0
        # burnout_gain = 5.0 * 0.1 (burnout_conversion_rate) = 0.5
        expected_burnout_gain = 0.5

        # ACT
        outcomes = shoot_results_calculator.calculate_talent_outcomes(
            scene_data, [talent], [], bloc_context_data
        )

        # ASSERT
        assert len(outcomes) == 1
        outcome = outcomes[0]
        assert outcome.burnout_gain == pytest.approx(expected_burnout_gain)

    def test_ds_skill_gain_dom_talent_dom_scene(self, shoot_results_calculator, talent_data, scene_data, bloc_context_data, mock_scene_calc_config):
        """
        Tests D/S skill gain for a Dom talent in a Dom-focused scene.
        """
        # ARRANGE
        talent = talent_data
        talent.id = 1
        scene_data.final_cast = {"101": 1}
        scene_data.dom_sub_dynamic_level = 3 # Dom-focused scene
        vp = scene_data.virtual_performers[0]
        vp.disposition = "Dom" # Talent matching disposition

        # Manual calculation for DS Skill Gain:
        # base_gain = runtime * base_rate * level_multiplier = 20 * 0.005 * 1.2 = 0.12
        # dom_focus = 1.0 (for scene level 3) * 1.2 (disposition multiplier) = 1.2
        # sub_focus = 0.0 (for scene level 3)
        # total_focus = 1.2 + 0.0 = 1.2
        # dom_gain = 0.12 * (1.2 / 1.2) = 0.12
        # sub_gain = 0.12 * (0.0 / 1.2) = 0.0
        expected_dom_gain = 0.12
        expected_sub_gain = 0.0

        # ACT
        outcomes = shoot_results_calculator.calculate_talent_outcomes(
            scene_data, [talent], [], bloc_context_data
        )

        # ASSERT
        assert len(outcomes) == 1
        outcome = outcomes[0]
        assert outcome.skill_gains['dom_skill'] == pytest.approx(expected_dom_gain)
        assert outcome.skill_gains['sub_skill'] == pytest.approx(expected_sub_gain)

    def test_talent_crew_assignment_stress(self, shoot_results_calculator, talent_data, scene_data, bloc_context_data, mock_stress_calculator):
        """
        Tests that a talent assigned to a crew job has their job listed for stress calculation.
        """
        # ARRANGE
        talent = talent_data
        talent.id = 1
        scene_data.final_cast = {"101": 1}
        bloc_context_data['crew_assignments'] = {
            'director': {'type': 'character', 'id': 1} # Talent 1 is also the director
        }

        # ACT
        shoot_results_calculator.calculate_talent_outcomes(
            scene_data, [talent], [], bloc_context_data
        )

        # ASSERT
        # Verify that calculate_stress_gain was called with the correct jobs
        mock_stress_calculator.calculate_stress_gain.assert_called_once()
        args, kwargs = mock_stress_calculator.calculate_stress_gain.call_args
        assert 'jobs' in kwargs
        assert 'actor' in kwargs['jobs']
        assert 'director' in kwargs['jobs']


class TestEstimateFatigueGain:
    """Tests for the estimate_fatigue_gain method."""

    def test_no_fatigue_gain_if_stamina_cost_less_than_max_stamina(self, shoot_results_calculator, talent_data, scene_data, mock_scene_calc_config, mock_role_performance_calculator):
        """
        Tests that no fatigue is gained if the stamina cost is within the talent's pool.
        """
        # ARRANGE
        talent = talent_data
        talent.stamina = 10.0 # Max stamina = 10 * 10 = 100
        vp_id = 101

        # Stamina cost for VP 101 from scene_data (sum of segment runtimes * modifier)
        # = (20 * 0.5 * 1.0) + (20 * 0.5 * 1.0) = 10 + 10 = 20.0
        # 20.0 < 100, so no fatigue gain
        
        # ACT
        fatigue_gain = shoot_results_calculator.estimate_fatigue_gain(talent, scene_data, vp_id)

        # ASSERT
        assert fatigue_gain == 0

    def test_fatigue_gain_calculation_overdraw(self, shoot_results_calculator, talent_data, scene_data, mock_scene_calc_config, mock_role_performance_calculator):
        """
        Tests correct fatigue gain when stamina is overdrawn.
        """
        # ARRANGE
        talent = talent_data
        talent.stamina = 1.0 # Max stamina = 1 * 10 = 10.0
        vp_id = 101

        # Stamina cost = 20.0
        # max_stamina = 10.0
        # overdraw_ratio = (20.0 - 10.0) / 10.0 = 1.0
        # fatigue_gain = min(100, int(1.0 * 100)) = 100
        expected_fatigue_gain = 100

        # ACT
        fatigue_gain = shoot_results_calculator.estimate_fatigue_gain(talent, scene_data, vp_id)

        # ASSERT
        assert fatigue_gain == expected_fatigue_gain

    def test_fatigue_gain_clamps_at_100(self, shoot_results_calculator, talent_data, scene_data, mock_scene_calc_config, mock_role_performance_calculator):
        """
        Tests that fatigue gain is clamped at a maximum of 100.
        """
        # ARRANGE
        talent = talent_data
        talent.stamina = 0.1 # Max stamina = 0.1 * 10 = 1.0
        vp_id = 101

        # Stamina cost = 20.0
        # max_stamina = 1.0
        # overdraw_ratio = (20.0 - 1.0) / 1.0 = 19.0
        # fatigue_gain = min(100, int(19.0 * 100)) = 100 (clamped)
        expected_fatigue_gain = 100

        # ACT
        fatigue_gain = shoot_results_calculator.estimate_fatigue_gain(talent, scene_data, vp_id)

        # ASSERT
        assert fatigue_gain == expected_fatigue_gain

    def test_fatigue_gain_with_different_stamina_modifiers(self, shoot_results_calculator, talent_data, scene_data, mock_scene_calc_config, mock_role_performance_calculator, mock_data_manager):
        """
        Tests fatigue gain when role performance calculator returns different modifiers.
        """
        # ARRANGE
        talent = talent_data
        talent.stamina = 5.0 # Max stamina = 5 * 10 = 50.0
        vp_id = 101

        # Mock the `get_role_stamina_modifier` to return different values
        mock_role_performance_calculator.get_role_stamina_modifier.side_effect = [
            0.5, # for tag_A
            2.0  # for tag_B
        ]
        # Recalculate expanded action segments to ensure mock is used correctly
        scene_data.get_expanded_action_segments.return_value = [
            ActionSegment(tag_name="tag_A", runtime_percentage=50,
                          slot_assignments=[SlotAssignment(slot_id="tag_A_role_1", virtual_performer_id=vp_id)]),
            ActionSegment(tag_name="tag_B", runtime_percentage=50,
                          slot_assignments=[SlotAssignment(slot_id="tag_B_role_1", virtual_performer_id=vp_id)])
        ]

        # Stamina cost for VP 101:
        # tag_A: runtime 10 * modifier 0.5 = 5.0
        # tag_B: runtime 10 * modifier 2.0 = 20.0
        # Total stamina cost = 5.0 + 20.0 = 25.0
        # max_stamina = 50.0
        # 25.0 < 50.0, so no fatigue gain
        expected_fatigue_gain = 0

        # ACT
        fatigue_gain = shoot_results_calculator.estimate_fatigue_gain(talent, scene_data, vp_id)

        # ASSERT
        assert fatigue_gain == expected_fatigue_gain
        mock_role_performance_calculator.get_role_stamina_modifier.assert_has_calls([
            call(scene_data.get_expanded_action_segments()[0], vp_id, scene_data, mock_data_manager.tag_definitions),
            call(scene_data.get_expanded_action_segments()[1], vp_id, scene_data, mock_data_manager.tag_definitions)
        ])
