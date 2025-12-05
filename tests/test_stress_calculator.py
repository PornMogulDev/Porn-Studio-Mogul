import pytest
from unittest.mock import MagicMock

from src.services.calculation.stress_calculator import StressCalculator
from src.services.calculation.trait_modifier_resolver import TraitModifierResolver
from src.services.models.configs import SceneCalculationConfig
from src.data.game_state import Talent


def talent_factory(traits: list[str]) -> Talent:
    """Factory to create a Talent instance with default values."""
    return Talent(
        id=1,
        alias="Test Talent",
        age=25,
        gender="Female",
        nationality="American",
        primary_ethnicity="Caucasian",
        performance=50,
        acting=50,
        stamina=50,
        dom_skill=50,
        sub_skill=50,
        ambition=5,
        traits=traits,
        ds_dynamic_preferences={},
    )


@pytest.fixture
def data_manager():
    """Returns a mock DataManager with introvert trait."""
    dm = MagicMock()
    dm.get_trait_definition.side_effect = lambda trait_id: {
        "introvert": {
            "id": "introvert", "name": "Introvert", "type": "personality",
            "stress_modifiers": {
                "location_tag_penalties": {"Public": 20},
                "policy_penalties": {"policy_open_set": 15},
                "cast_size_penalty_scalar": 5
            }
        },
        "workaholic": {
            "id": "workaholic", "name": "Workaholic", "type": "behavioral"
        }
    }.get(trait_id)

    dm.production_jobs.get.side_effect = lambda job_id: {
        "camera": {"base_stress_load": 10}
    }.get(job_id)

    return dm


@pytest.fixture
def scene_calc_config():
    """Returns a default SceneCalculationConfig."""
    return SceneCalculationConfig(
        base_acting_stress=10,
        multitasking_stress_multiplier=0.5,
        craft_services_stress_relief_scalar=0.1,
        stamina_to_pool_multiplier=0,
        in_scene_penalty_scalar=0,
        fatigue_penalty_scalar=0,
        fatigue_passive_decay_rate=0,
        fatigue_active_recovery_bonus=0,
        fatigue_stamina_recovery_modifier=0,
        max_stress_threshold=100.0,
        burnout_conversion_rate=0,
        maximum_skill_level=100,
        skill_gain_base_rate=0,
        skill_gain_curve_steepness=0,
        exp_gain_base_rate=0,
        exp_gain_curve_steepness=0,
        ds_skill_gain_base_rate=0,
        ds_skill_gain_disposition_multiplier=0,
        ds_skill_gain_dynamic_level_multipliers={},
        age_based_affinity_rules=[],
        popularity_gain_scalar=0,
        scene_quality_base_acting_weight=0,
        scene_quality_min_acting_weight=0,
        scene_quality_max_acting_weight=0,
        protagonist_contribution_weight=0,
        chemistry_performance_scalar=0,
        scene_quality_ds_weights={},
        scene_quality_min_performance_modifier=0,
        scene_quality_auto_tag_default_quality=0,
        base_release_revenue=0,
        star_power_revenue_scalar=0,
        saturation_spend_rate=0,
        default_sentiment_multiplier=0,
        revenue_weight_focused_physical_tag=0,
        revenue_weight_default_action_appeal=0,
        revenue_weight_auto_tag=0,
        revenue_penalties={}
    )


@pytest.fixture
def stress_calculator(data_manager, scene_calc_config):
    """Returns a StressCalculator instance."""
    trait_resolver = TraitModifierResolver(data_manager)
    return StressCalculator(data_manager, scene_calc_config, trait_resolver)


class TestStressCalculator:
    def test_base_stress(self, stress_calculator):
        """Tests base stress for a single acting job."""
        talent = talent_factory(traits=[])
        stress = stress_calculator.calculate_stress_gain(
            talent=talent, jobs=["actor"], location_def={},
            craft_services_efficiency=1.0, health_safety_score=100,
            active_policies=[], cast_size=1
        )
        assert stress == pytest.approx(9.9)  # 10 base - 0.1 relief

    def test_introvert_public_location(self, stress_calculator):
        """Tests introvert stress penalty in public locations."""
        talent = talent_factory(traits=["introvert"])
        location = {"tags": ["Public"]}
        stress = stress_calculator.calculate_stress_gain(
            talent=talent, jobs=["actor"], location_def=location,
            craft_services_efficiency=0, health_safety_score=100,
            active_policies=[], cast_size=1
        )
        # 10 base + 20 public penalty + 5 cast size penalty
        assert stress == pytest.approx(35)

    def test_introvert_open_set_policy(self, stress_calculator):
        """Tests introvert stress penalty with open set policy."""
        talent = talent_factory(traits=["introvert"])
        policies = ["policy_open_set"]
        stress = stress_calculator.calculate_stress_gain(
            talent=talent, jobs=["actor"], location_def={},
            craft_services_efficiency=0, health_safety_score=100,
            active_policies=policies, cast_size=1
        )
        # 10 base + 15 policy penalty + 5 cast size penalty
        assert stress == pytest.approx(30)

    def test_introvert_cast_size_penalty(self, stress_calculator):
        """Tests introvert stress penalty based on cast size."""
        talent = talent_factory(traits=["introvert"])
        stress = stress_calculator.calculate_stress_gain(
            talent=talent, jobs=["actor"], location_def={},
            craft_services_efficiency=0, health_safety_score=100,
            active_policies=[], cast_size=4
        )
        # 10 base + (4 * 5) cast size penalty
        assert stress == pytest.approx(30)

    def test_introvert_all_penalties(self, stress_calculator):
        """Tests introvert with all penalties combined."""
        talent = talent_factory(traits=["introvert"])
        location = {"tags": ["Public"]}
        policies = ["policy_open_set"]
        stress = stress_calculator.calculate_stress_gain(
            talent=talent, jobs=["actor"], location_def=location,
            craft_services_efficiency=0, health_safety_score=100,
            active_policies=policies, cast_size=3
        )
        # 10 base + 20 public + 15 policy + (3 * 5) cast size
        assert stress == pytest.approx(60)

    def test_multitasking_penalty(self, stress_calculator):
        """Tests stress penalty for multitasking."""
        talent = talent_factory(traits=[])
        jobs = ["actor", "camera"]
        stress = stress_calculator.calculate_stress_gain(
            talent=talent, jobs=jobs, location_def={},
            craft_services_efficiency=0, health_safety_score=100,
            active_policies=[], cast_size=1
        )
        # (10 acting + 10 camera) * 1.5 multitask multiplier
        assert stress == pytest.approx(30)

    def test_multitasking_penalty_workaholic(self, stress_calculator):
        """Tests that workaholic trait negates multitasking penalty."""
        talent = talent_factory(traits=["workaholic"])
        jobs = ["actor", "camera"]
        stress = stress_calculator.calculate_stress_gain(
            talent=talent, jobs=jobs, location_def={},
            craft_services_efficiency=0, health_safety_score=100,
            active_policies=[], cast_size=1
        )
        # (10 acting + 10 camera) * 1.0 (no multiplier)
        assert stress == pytest.approx(20)

    def test_health_safety_multiplier(self, stress_calculator):
        """Tests that a low H&S score increases stress."""
        talent = talent_factory(traits=[])
        stress = stress_calculator.calculate_stress_gain(
            talent=talent, jobs=["actor"], location_def={},
            craft_services_efficiency=0, health_safety_score=0,
            active_policies=[], cast_size=1
        )
        # 10 base * 2.0 H&S multiplier
        assert stress == pytest.approx(20)

    def test_craft_services_relief(self, stress_calculator):
        """Tests that craft services reduces stress."""
        talent = talent_factory(traits=[])
        stress = stress_calculator.calculate_stress_gain(
            talent=talent, jobs=["actor"], location_def={},
            craft_services_efficiency=2.0, health_safety_score=100,
            active_policies=[], cast_size=1
        )
        # 10 base - (0.1 * 2.0) relief
        assert stress == pytest.approx(9.8)

    def test_stress_is_never_negative(self, stress_calculator):
        """Tests that stress gain cannot be negative."""
        talent = talent_factory(traits=[])
        stress = stress_calculator.calculate_stress_gain(
            talent=talent, jobs=[], location_def={},
            craft_services_efficiency=1000.0, health_safety_score=100,
            active_policies=[], cast_size=1
        )
        assert stress == 0.0

