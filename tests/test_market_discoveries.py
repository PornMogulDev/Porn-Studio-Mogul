from types import SimpleNamespace
from unittest.mock import Mock, create_autospec

import pytest

from database.db_models import MarketGroupStateDB, SceneDB, StudioStateDB
from services.calculation.market_group_resolver import MarketGroupResolver
from services.calculation.revenue_calculator import RevenueCalculator
from services.command.email_service import EmailService
from services.command.scene_command_service import SceneCommandService
from services.command.scene_processing_service import SceneProcessingService
from services.command.talent_command_service import TalentCommandService
from services.market_service import MarketService
from services.models.configs import MarketConfig
from services.models.inputs import ContentTagInput, RevenueInput
from services.models.results import SceneRevenueResult
from services.query.game_query_service import GameQueryService


def test_release_scene_processes_and_saves_discoveries(game_session_factory):
    group = "Straight Men"
    tag = "Big Boobs"
    with game_session_factory.begin() as session:
        session.add_all([
            MarketGroupStateDB(name=group, current_saturation=1.0),
            SceneDB(
                id=1,
                title="Test Scene",
                status="ready_to_release",
                focus_target=group,
                scheduled_absolute_week=1,
                assigned_tags={tag: [1]},
            ),
            StudioStateDB(id=1, money=50_000),
        ])

    market_data = {"viewer_groups": [{
        "name": group,
        "preferences": {"physical_sentiments": {tag: 2.5}},
    }]}
    market_service = MarketService(
        market_group_resolver=MarketGroupResolver(market_data),
        tag_definitions={tag: {"type": "Physical"}},
        config=MarketConfig(
            saturation_recovery_rate=0.1,
            discovery_interest_threshold=0.5,
            discoveries_per_scene=5,
        ),
    )
    scene_processor = create_autospec(SceneProcessingService, instance=True)
    scene_processor.prepare_revenue_input.return_value = RevenueInput(
        title="Test Scene",
        focus_target=group,
        dom_sub_level=0,
        total_runtime_minutes=10,
        content_tags=[ContentTagInput(tag, "Physical", quality=0.8, weight=5.0)],
    )
    revenue_calculator = create_autospec(RevenueCalculator, instance=True)
    revenue_calculator.calculate_revenue.return_value = SceneRevenueResult(
        total_revenue=1_000,
        viewer_group_interest={group: 1.0},
        revenue_modifier_details={},
        market_saturation_updates={group: 0.1},
    )
    signals = SimpleNamespace(emails_changed=Mock())
    email_service = create_autospec(EmailService, instance=True)
    scene_command_service = SceneCommandService(
        session_factory=game_session_factory,
        signals=signals,
        data_manager=None,
        query_service=GameQueryService(game_session_factory),
        talent_command_service=create_autospec(TalentCommandService, instance=True),
        market_service=market_service,
        email_service=email_service,
        scene_processing_service=scene_processor,
        revenue_calculator=revenue_calculator,
        scene_event_trigger_service=None,
        bloc_cost_calculator=None,
        crew_skill_calculator=None,
    )

    result = scene_command_service.release_scene(scene_id=1)

    assert result["market_changed"] is True
    assert result["discoveries"] == {group: [tag]}
    with game_session_factory() as session:
        market_state = session.get(MarketGroupStateDB, group)
        assert market_state.discovered_sentiments == {"physical_sentiments": [tag]}
        assert market_state.current_saturation == pytest.approx(0.9)
        scene = session.get(SceneDB, 1)
        assert scene.status == "released"
        assert scene.revenue == 1_000
        assert session.get(StudioStateDB, 1).money == 51_000
    email_service.create_market_discovery_email.assert_called_once()
    assert email_service.create_market_discovery_email.call_args.args[1:] == (
        "Test Scene", {group: [tag]},
    )
    signals.emails_changed.emit.assert_called_once_with()
