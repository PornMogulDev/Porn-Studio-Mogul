from unittest.mock import Mock

import pytest

from database.db_models import GameInfoDB, MarketGroupStateDB, StudioStateDB
from services.calculation.market_group_resolver import MarketGroupResolver
from services.market_service import MarketService
from services.models.configs import MarketConfig
from services.time_service import TimeService


def test_failed_week_rolls_back_money_and_market_before_retry(game_session_factory):
    with game_session_factory.begin() as session:
        session.add_all([
            GameInfoDB(key="absolute_week", value="1"),
            StudioStateDB(id=1, money=1_000),
            MarketGroupStateDB(name="Test Group", current_saturation=0.5),
        ])

    def pay_contracts(session, absolute_week):
        session.get(StudioStateDB, 1).money -= 100

    def fail_after_writes(session, absolute_week):
        session.flush()
        raise RuntimeError("AI update failed")

    contracts = Mock()
    contracts.process_weekly_contracts.side_effect = pay_contracts
    ai_director = Mock()
    ai_director.process_weekly_ai_decisions.side_effect = fail_after_writes
    scenes = Mock()
    scenes.process_weekly_post_production.return_value = []
    talent = Mock()
    talent.process_weekly_updates.return_value = False
    tours = Mock()
    tours.process_autonomous_tour_decisions.return_value = False

    time_service = TimeService(
        session_factory=game_session_factory,
        signals=Mock(),
        scene_command_service=scenes,
        talent_command_service=talent,
        market_service=MarketService(
            market_group_resolver=MarketGroupResolver({}),
            tag_definitions={},
            config=MarketConfig(0.1, 0.5, 5),
        ),
        tour_command_service=tours,
        contract_service=contracts,
        ai_studio_director=ai_director,
    )

    failed = time_service.advance_week()

    assert failed.was_paused
    assert failed.new_absolute_week == 1
    assert failed.new_money == 1_000
    with game_session_factory() as session:
        assert session.get(GameInfoDB, "absolute_week").value == "1"
        assert session.get(StudioStateDB, 1).money == 1_000
        assert session.get(MarketGroupStateDB, "Test Group").current_saturation == 0.5

    ai_director.process_weekly_ai_decisions.side_effect = None
    retry = time_service.advance_week()

    assert not retry.was_paused
    assert retry.new_absolute_week == 2
    assert retry.new_money == 900
    with game_session_factory() as session:
        assert session.get(GameInfoDB, "absolute_week").value == "2"
        assert session.get(StudioStateDB, 1).money == 900
        assert session.get(MarketGroupStateDB, "Test Group").current_saturation == pytest.approx(0.55)
