import pytest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
import json

from services.market_group_resolver import MarketGroupResolver
from services.market_service import MarketService
from data.game_state import Scene, MarketGroupState, ActionSegment
from database.db_models import Base, MarketGroupStateDB

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

MARKET_DATA = {
  "viewer_groups": [
    {
      "name": "Straight Men",
      "preferences": {
        "orientation_sentiments": {"Straight": 2.0, "Gay": 0.0},
        "action_sentiments": {"Vaginal": 2.5, "Masturbation": 0.8},
        "thematic_sentiments": {"Boobs Worship": 1.2},
        "physical_sentiments": {"Big Boobs": 2.5, "Interracial (WM/AF)": 1.8}
      },
      "popularity_spillover": {"Gay Men": 0.10}
    },
    {
      "name": "Blowjob Enthusiasts",
      "inherits_from": "Straight Men",
      "preferences": {
        "action_sentiments": {
          "Blowjob": 3.5,
          "Vaginal": 1.0
        },
        "physical_sentiments": {"Big Boobs": 3.0}
      }
    },
    {
      "name": "Gay Men",
      "preferences": {"action_sentiments": {"Anal": 2.0}}
    }
  ]
}

THEMATIC_TAGS = [
    {"name": "Boobs Worship", "type": "Thematic"},
    {"name": "Raceplay", "type": "Thematic"}
]

PHYSICAL_TAGS = [
    {"name": "Big Boobs", "type": "Physical"},
    {"name": "Interracial (WM/AF)", "type": "Physical"}
]

ACTION_TAGS = [
    {"name": "Vaginal", "type": "Action", "orientation": "Straight"},
    {"name": "Blowjob", "type": "Action", "orientation": "Straight"},
    {"name": "Anal", "type": "Action", "orientation": "Gay"}
]
#endregion

#region Pytest Fixtures
@pytest.fixture(scope="module")
def sample_market_data():
    """Provides static market definition data for testing."""
    return MARKET_DATA

@pytest.fixture(scope="module")
def sample_tag_definitions():
    """Provides a consolidated dictionary of all tag definitions."""
    all_tags = {}
    for tag_list in [THEMATIC_TAGS, PHYSICAL_TAGS, ACTION_TAGS]:
        for tag in tag_list:
            all_tags[tag['name']] = tag
    return all_tags

@pytest.fixture
def db_session():
    """Creates a fresh, in-memory SQLite database for each test."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

@pytest.fixture
def market_group_resolver(sample_market_data):
    """Provides an instance of the resolver with the new market data."""
    return MarketGroupResolver(sample_market_data)

@pytest.fixture
def market_service(db_session, market_group_resolver, sample_tag_definitions):
    """Provides a MarketService instance with mocked dependencies."""
    mock_config = SimpleNamespace(saturation_recovery_rate=0.05)
    return MarketService(
        db_session=db_session,
        market_group_resolver=market_group_resolver,
        tag_definitions=sample_tag_definitions,
        config=mock_config
    )
#endregion

#region Unit Tests for MarketGroupResolver (Pure Logic)
class TestMarketGroupResolver:
    """
    Tests the pure, stateless logic of resolving market group inheritance.
    This does not touch the database.
    """
    def test_resolve_group_no_inheritance(self, market_group_resolver):
        resolved = market_group_resolver.get_resolved_group("Straight Men")
        assert resolved['name'] == "Straight Men"
        assert "inherits_from" not in resolved
        assert resolved['preferences']['action_sentiments']['Vaginal'] == 2.5
        assert resolved['preferences']['thematic_sentiments']['Boobs Worship'] == 1.2

    def test_resolve_group_with_inheritance(self, market_group_resolver):
        """
        Tests deep-merging of preferences where child values overwrite parent values.
        """
        resolved = market_group_resolver.get_resolved_group("Blowjob Enthusiasts")

        # 1. Child OVERWRITES parent value
        # Parent (Straight Men) has Vaginal: 2.5, Child has Vaginal: 1.0
        assert resolved['preferences']['action_sentiments']['Vaginal'] == 1.0
        # Parent has Big Boobs: 2.5, Child has Big Boobs: 3.0
        assert resolved['preferences']['physical_sentiments']['Big Boobs'] == 3.0

        # 2. Child ADDS new value
        # Parent does not have Blowjob sentiment, Child adds it.
        assert resolved['preferences']['action_sentiments']['Blowjob'] == 3.5

        # 3. Child INHERITS parent value
        # Parent has Masturbation: 0.8, Child does not define it.
        assert resolved['preferences']['action_sentiments']['Masturbation'] == 0.8
        # Parent has Boobs Worship, Child does not define any thematic_sentiments.
        assert resolved['preferences']['thematic_sentiments']['Boobs Worship'] == 1.2

        # 4. Child INHERITS entire preference category from parent
        # Parent defines 'orientation_sentiments', Child does not.
        assert 'orientation_sentiments' in resolved['preferences']
        assert resolved['preferences']['orientation_sentiments']['Straight'] == 2.0

    def test_resolve_group_returns_empty_for_nonexistent(self, market_group_resolver):
        assert market_group_resolver.get_resolved_group("Imaginary Fans") == {}

    def test_circular_dependency_raises_error(self):
        bad_data = {
            "viewer_groups": [
                {"name": "A", "inherits_from": "B"},
                {"name": "B", "inherits_from": "A"},
            ]
        }
        with pytest.raises(RecursionError, match="Circular inheritance detected"):
            MarketGroupResolver(bad_data)
#endregion

#region Integration Tests for MarketService (DB Interactions)
class TestMarketServiceDB:
    """
    Tests the service's interaction with the SQLAlchemy session,
    covering data persistence, retrieval, and transaction management (commits/rollbacks).
    """
    def test_get_all_market_states_empty_db(self, market_service):
        states = market_service.get_all_market_states()
        assert states == {}

    def test_get_all_market_states_with_data(self, market_service, db_session):
        # Arrange
        db_session.add(MarketGroupStateDB(name="Straight Men", current_saturation=0.8))
        db_session.add(MarketGroupStateDB(name="Gay Men", current_saturation=1.0))
        db_session.commit()

        # Act
        states = market_service.get_all_market_states()

        # Assert
        assert len(states) == 2
        assert isinstance(states["Straight Men"], MarketGroupState)
        assert states["Straight Men"].current_saturation == 0.8
        assert states["Gay Men"].name == "Gay Men"

    def test_recover_saturation_changes_value_and_commits(self, market_service, db_session):
        # Arrange
        db_session.add(MarketGroupStateDB(name="Straight Men", current_saturation=0.5))
        db_session.commit()

        # Act
        changed = market_service.recover_all_market_saturation()
        
        # Assert: Check the logic
        assert changed is True
        recovered_group = db_session.query(MarketGroupStateDB).filter_by(name="Straight Men").one()
        # saturation' = saturation + (1 - saturation) * rate
        # 0.525 = 0.5 + (1.0 - 0.5) * 0.05
        assert recovered_group.current_saturation == pytest.approx(0.525)

    def test_recover_saturation_at_max_makes_no_change(self, market_service, db_session):
        # Arrange
        db_session.add(MarketGroupStateDB(name="Saturated Group", current_saturation=1.0))
        db_session.commit()

        # Act
        changed = market_service.recover_all_market_saturation()

        # Assert
        assert changed is False
        group = db_session.query(MarketGroupStateDB).filter_by(name="Saturated Group").one()
        assert group.current_saturation == 1.0

    def test_recover_saturation_rollback_on_error(self, market_service, db_session):
        # Arrange
        db_session.add(MarketGroupStateDB(name="Good Group", current_saturation=0.5))
        db_session.commit()
        initial_value = 0.5
        
        # Mock session.commit to raise a database error
        with patch.object(market_service.session, 'commit', side_effect=Exception("DB Commit Error")) as mock_commit:
            with patch.object(market_service.session, 'rollback') as mock_rollback:
                # Act
                changed = market_service.recover_all_market_saturation()

                # Assert
                assert changed is False # Operation failed, so no change was ultimately made
                mock_commit.assert_called_once()
                mock_rollback.assert_called_once() # Ensure rollback was called on error

                # Verify the session is clean and the object holds its original value
                db_session.expire_all() # Force a re-read from the DB
                group = db_session.query(MarketGroupStateDB).filter_by(name="Good Group").one()
                assert group.current_saturation == initial_value
#endregion

#region Mock-based Tests for Asynchronous/Complex Interactions
class TestMarketServiceLogic:
    """
    Tests complex service logic that depends on multiple data sources (game state, definitions).
    Mocks are used to isolate the logic being tested from its dependencies.
    """
    def test_get_potential_discoveries(self, market_service):
        # Arrange: Create a mock Scene object with various tags.
        mock_scene = Scene(
            id=1, title="Test Scene", status="shot", focus_target="Straight Men",
            scheduled_week=1, scheduled_year=1,
            global_tags=["Boobs Worship", "Unknown Tag"], # Thematic
            assigned_tags={"Interracial (WM/AF)": [1,2]}, # Physical
            action_segments=[ActionSegment(tag="Vaginal")] # Action
        )
        
        # Act
        discoveries = market_service.get_potential_discoveries(mock_scene, "Straight Men")
        
        # Assert
        assert len(discoveries) == 3 # "Unknown Tag" should be ignored
        
        # For easier assertion, convert list of dicts to a dict keyed by tag name
        discoveries_by_tag = {d['tag']: d for d in discoveries}
        
        # 1. Test Thematic Tag Discovery
        boobs_discovery = discoveries_by_tag.get("Boobs Worship")
        assert boobs_discovery is not None
        assert boobs_discovery['type'] == 'thematic_sentiments'
        # From MARKET_DATA for "Straight Men": "Boobs Worship": 1.2
        assert boobs_discovery['impact'] == 1.2
        
        # 2. Test Physical Tag Discovery
        interracial_discovery = discoveries_by_tag.get("Interracial (WM/AF)")
        assert interracial_discovery is not None
        assert interracial_discovery['type'] == 'physical_sentiments'
        # From MARKET_DATA for "Straight Men": "Interracial (WM/AF)": 1.8
        # Assuming game logic for impact is |preference - 1.0|
        assert interracial_discovery['impact'] == pytest.approx(abs(1.8 - 1.0))

        # 3. Test Action Tag Discovery
        vaginal_discovery = discoveries_by_tag.get("Vaginal")
        assert vaginal_discovery is not None
        assert vaginal_discovery['type'] == 'action_sentiments'
        # From MARKET_DATA for "Straight Men": "Vaginal": 2.5
        assert vaginal_discovery['impact'] == 2.5
#endregion