from unittest.mock import Mock

import pytest

from data.data_manager import DataManager
from database.db_models import SceneDB, StudioStateDB, TalentDB, VirtualPerformerDB
from services.calculation.talent_availability_checker import AvailabilityResult
from services.query.game_query_service import GameQueryService
from services.query.talent_query_service import TalentQueryService


@pytest.fixture(scope="module")
def game_data():
    manager = DataManager()
    yield manager
    manager.conn.close()


@pytest.mark.parametrize(
    ("requirement", "filters", "expected_ids"),
    [
        pytest.param("White", {}, {1, 2, 3}, id="parent-with-legacy-parent-value"),
        pytest.param("Asian", {}, {4, 5}, id="parent-with-child-values-only"),
        pytest.param("Western European", {}, {2}, id="specific-subgroup"),
        pytest.param("Black", {}, {6}, id="group-with-no-subgroups"),
        pytest.param(
            "White", {"ethnicities": ["East Asian"], "age_min": 30}, {3}, id="role-overrides-manual-list",
        ),
        pytest.param("Asian", {"ethnicity": "Black"}, {4, 5}, id="role-overrides-single-filter"),
        pytest.param("Any", {"ethnicities": ["East Asian"]}, {4}, id="unrestricted-role-with-manual-filter"),
        pytest.param("Any", {}, {1, 2, 3, 4, 5, 6}, id="unrestricted-role"),
    ],
)
def test_role_ethnicity_matches_the_required_group(game_session_factory, game_data, requirement, filters, expected_ids):
    with game_session_factory.begin() as session:
        scene = SceneDB(id=1, title="Test role", status="casting", focus_target="Test Group", scheduled_absolute_week=2)
        scene.virtual_performers = [VirtualPerformerDB(id=1, name="Role", gender="Female", ethnicity=requirement)]
        session.add_all([
            scene,
            StudioStateDB(id=1, location="Test Studio"),
            TalentDB(id=1, alias="A", gender="Female", age=25, ethnicity="White"),
            TalentDB(id=2, alias="B", gender="Female", age=24, ethnicity="Western European"),
            TalentDB(id=3, alias="C", gender="Female", age=35, ethnicity="Eastern European"),
            TalentDB(id=4, alias="D", gender="Female", age=25, ethnicity="East Asian"),
            TalentDB(id=5, alias="E", gender="Female", age=28, ethnicity="South Asian"),
            TalentDB(id=6, alias="F", gender="Female", age=32, ethnicity="Black"),
            TalentDB(id=7, alias="G", gender="Male", age=34, ethnicity="Western European"),
        ])

    service = TalentQueryService(
        session_factory=game_session_factory,
        data_manager=game_data,
        query_service=GameQueryService(game_session_factory),
        location_service=None,
        demand_calculator=None,
        config=None,
        availability_checker=Mock(check=Mock(return_value=AvailabilityResult(True))),
        shoot_results_calculator=Mock(estimate_fatigue_gain=Mock(return_value=0)),
        status_calculator=None,
    )

    candidates = service.get_eligible_talent_for_role(scene_id=1, vp_id=1, filters=filters)

    assert {candidate.id for candidate in candidates} == expected_ids
