from tempfile import TemporaryDirectory

import pytest


def pytest_configure(config):
    # Application modules resolve player data paths at import time.
    player_data = TemporaryDirectory(prefix="psm-test-")
    environment = pytest.MonkeyPatch()
    environment.setenv("PSM_USER_DATA_DIR", player_data.name)
    config.add_cleanup(player_data.cleanup)
    config.add_cleanup(environment.undo)


@pytest.fixture
def game_session_factory(tmp_path):
    """Use a fresh, file-backed game database for persistence checks."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from database.db_models import Base

    engine = create_engine(f"sqlite:///{tmp_path / 'game.sqlite'}")
    try:
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine)
    finally:
        engine.dispose()
