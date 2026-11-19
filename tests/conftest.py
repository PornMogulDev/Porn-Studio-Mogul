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


@pytest.fixture
def saves(monkeypatch, tmp_path):
    from data import save_manager

    monkeypatch.setattr(save_manager, "SAVE_DIR", tmp_path / "saves")
    manager = save_manager.SaveManager()
    yield manager
    manager.cleanup_session_file()


@pytest.fixture(scope="module")
def qt_app():
    from PyQt6.QtWidgets import QApplication

    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("QT_QPA_PLATFORM", "offscreen")
        app = QApplication.instance() or QApplication([])
        yield app


@pytest.fixture
def window(qt_app, saves, monkeypatch, tmp_path):
    from PyQt6.QtCore import QCoreApplication, QEvent

    from app.application import ApplicationWindow
    from data import settings_manager

    monkeypatch.setattr(settings_manager, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings_manager.SettingsManager, "_instance", None)
    main = ApplicationWindow()
    main.controller.new_game_started()
    yield main
    main.settings_manager.set_setting("save_on_exit", False)
    main.close()
    main.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
