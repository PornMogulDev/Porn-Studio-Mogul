import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.orm.attributes import flag_modified  # We'll need this later for the fix
from collections import defaultdict

# --- Import all necessary components from your project ---
from database.db_models import Base, MarketGroupStateDB, SceneDB, GameInfoDB
from data.game_state import Scene, MarketGroupState
from services.market_service import MarketService
from services.command.scene_command_service import SceneCommandService

# --- Mock Dependencies that aren't under test ---
# We create simple placeholder classes to satisfy the constructor of SceneCommandService
class MockRevenueCalculator:
    def calculate_revenue(self, scene, cast, markets, resolved_groups):
        # Return a result that will DEFINITELY trigger a discovery
        return type('RevenueResult', (), {
            'total_revenue': 1000,
            'viewer_group_interest': {'Straight Men': 1.0}, # Interest > threshold
            'market_saturation_updates': {'Straight Men': 0.1},
            'revenue_modifier_details': {}
        })

class MockGameQueryService:
    def get_all_market_states(self):
        # This will be replaced by the actual DB query inside the test
        return {}

class MockTalentCommandService:
    def update_popularity_from_scene(self, session, scene_id): pass

class MockEmailService:
    def create_market_discovery_email(self, session, title, discoveries): pass

# --- Pytest Fixtures for setting up the test environment ---

@pytest.fixture(scope="function")
def session():
    """Creates a fresh, in-memory database session for each test."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db_session = Session()
    yield db_session
    db_session.close()
    engine.dispose()

@pytest.fixture
def setup_data(session: Session):
    """Populates the test database with prerequisite data."""
    # Arrange: Create a market group with empty discoveries
    market_state = MarketGroupStateDB(
        name="Straight Men",
        current_saturation=1.0,
        discovered_sentiments={} # IMPORTANT: Starts empty
    )
    # Arrange: Create a scene that is ready to be released
    scene = SceneDB(
        id=1,
        title="Test Scene",
        status="ready_to_release",
        global_tags=["Big Boobs"] # A tag that can be discovered
    )
    # Arrange: Add starting money
    money = GameInfoDB(key="money", value="50000")
    
    session.add(market_state)
    session.add(scene)
    session.add(money)
    session.commit()


# --- The Actual Test ---

def test_release_scene_processes_and_saves_discoveries(session: Session, setup_data):
    """
    This test verifies that releasing a scene correctly updates the
    discovered_sentiments in the database and persists the change.
    """
    # --- ARRANGE ---
    
    # Create instances of our services, using mocks where needed
    mock_resolver = type('Resolver', (), {
        'get_resolved_group': lambda self, name: {
            'preferences': {
                'physical_sentiments': {'Big Boobs': 2.5}
            }
        },
        'get_all_resolved_groups': lambda self: {}
    })()
    
    mock_config = type('Config', (), {
        'discovery_interest_threshold': 0.5,
        'discoveries_per_scene': 5,
        'saturation_recovery_rate': 0.1
    })()

    # The MarketService must be the REAL implementation
    market_service = MarketService(
        market_group_resolver=mock_resolver,
        tag_definitions={'Big Boobs': {'type': 'Physical'}},
        config=mock_config
    )

    # A mock query service that just reads from our test DB
    class LiveQueryService(MockGameQueryService):
        def get_all_market_states(self):
            states_db = session.query(MarketGroupStateDB).all()
            return {s.name: s.to_dataclass(MarketGroupState) for s in states_db}

    # The SceneCommandService must be the REAL implementation
    scene_command_service = SceneCommandService(
        session_factory=lambda: session,
        signals=defaultdict(lambda: type('Signal', (), {'emit': lambda *args: None})), # Mock signals
        data_manager=None, # Not needed for this specific test path
        query_service=LiveQueryService(),
        talent_command_service=MockTalentCommandService(),
        market_service=market_service, # Use the real one
        email_service=MockEmailService(),
        scene_processing_service=None, # Not needed
        revenue_calculator=MockRevenueCalculator(),
        scene_event_trigger_service=None, # Not needed
        bloc_cost_calculator=None # Not needed
    )

    # --- ACT ---
    
    # Call the method we want to test
    result = scene_command_service.release_scene(scene_id=1)

    # --- ASSERT ---

    assert result is not None, "release_scene should return a result dictionary"
    assert result.get('market_changed') is True

    # Crucial check: Re-fetch the market state from the DB to see if it was saved
    session.commit() # Ensure any pending changes are flushed
    market_state_after = session.query(MarketGroupStateDB).get("Straight Men")
    
    assert market_state_after is not None
    
    # This is the assertion that will fail with the current code
    discovered = market_state_after.discovered_sentiments
    assert "physical_sentiments" in discovered
    assert "Big Boobs" in discovered["physical_sentiments"]