import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from PyQt6.QtCore import QCoreApplication, QEvent
from PyQt6.QtWidgets import QApplication

from app.application import ApplicationWindow
from data import save_manager, settings_manager
from database.db_models import GameInfoDB
from ui.presenters.talent_tab_presenter import TalentTabPresenter


@pytest.fixture
def saves(monkeypatch, tmp_path):
    monkeypatch.setattr(save_manager, "SAVE_DIR", tmp_path / "saves")
    manager = save_manager.SaveManager()
    yield manager
    manager.cleanup_session_file()


@pytest.fixture(scope="module")
def qt_app():
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("QT_QPA_PLATFORM", "offscreen")
        app = QApplication.instance() or QApplication([])
        yield app


@pytest.fixture
def window(qt_app, saves, monkeypatch, tmp_path):
    monkeypatch.setattr(settings_manager, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings_manager.SettingsManager, "_instance", None)
    main = ApplicationWindow()
    main.controller.new_game_started()
    yield main
    main.settings_manager.set_setting("save_on_exit", False)
    main.close()
    main.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)


@pytest.mark.parametrize("bad_save", ["missing", "corrupt", "empty", "incompatible"])
def test_failed_live_quick_load_preserves_the_active_game(window, bad_save):
    controller = window.controller
    saves = window.save_manager
    window.ui_manager.show_talent_profile_by_id(1)
    profile = window.ui_manager._talent_profile_window_singleton
    active_manager = saves.db_manager
    active_path = Path(saves.get_current_session_path())
    active_state = controller.game_state
    notifications = []
    controller.signals.notification_posted.connect(notifications.append)

    quicksave = saves.get_save_path(save_manager.QUICKSAVE_NAME)
    if bad_save == "corrupt":
        quicksave.write_bytes(b"not a SQLite database")
    elif bad_save in {"empty", "incompatible"}:
        with closing(sqlite3.connect(quicksave)) as database:
            if bad_save == "incompatible":
                database.execute("CREATE TABLE scenes (id INTEGER PRIMARY KEY)")

    controller.quick_load()

    assert saves.db_manager is active_manager
    assert Path(saves.get_current_session_path()) == active_path
    assert list(saves.save_dir.glob(".session-*")) == [active_path.parent]
    assert controller.game_state is active_state
    assert window.ui_manager._talent_profile_window_singleton is profile
    assert profile.isVisible()
    assert notifications and "Game quick loaded!" not in notifications
    controller.quick_save()
    assert notifications[-1] == "Game quick saved!"
    assert quicksave.is_file()
    controller.advance_week()
    assert controller.game_state.absolute_week == 2


def test_live_switch_closes_old_views_and_invalidates_requests(window):
    controller = window.controller
    saves = window.save_manager
    scene_id = controller.create_blank_scene(2)
    controller.save_game("Target")
    target_bytes = saves.get_save_path("Target").read_bytes()
    editor = controller.get_scene_state_editor(scene_id)
    editor.set_title("Unsaved in the target file")
    controller.update_scene_full(editor.finalize_for_saving())

    ui = window.ui_manager
    ui.show_talent_profile_by_id(1)
    ui.show_scene_planner(scene_id)
    old_profile = ui._talent_profile_window_singleton
    old_planner = ui._open_scene_dialogs[scene_id]
    old_path = Path(saves.get_current_session_path())
    old_factory = controller.query_service.session_factory
    talent_tab = next(presenter for presenter in ui.tab_presenters if isinstance(presenter, TalentTabPresenter))
    talent_tab.view.advanced_filters.update(scene_id=scene_id, vp_id=1, go_to_category_id=1)
    old_request = talent_tab._filter_sequence_id

    controller.load_game("Target")

    assert ui._talent_profile_window_singleton is None
    assert scene_id not in ui._open_scene_dialogs
    assert not old_profile.isVisible()
    assert not old_planner.isVisible()
    assert "scene_id" not in talent_tab.view.advanced_filters
    assert "go_to_category_id" not in talent_tab.view.advanced_filters
    talent_tab._on_demand_calculation_finished({1: 500}, old_request)
    assert talent_tab._demand_cache == {}
    assert controller.get_scene_by_id(scene_id).title != "Unsaved in the target file"
    assert saves.get_save_path("Target").read_bytes() == target_bytes
    assert not old_path.exists()
    with pytest.raises(ConnectionError):
        old_factory()

    # Qt can deliver destruction after replacement windows for the same IDs open.
    ui.show_talent_profile_by_id(1)
    ui.show_scene_planner(scene_id)
    replacement_profile = ui._talent_profile_window_singleton
    replacement_planner = ui._open_scene_dialogs[scene_id]
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    assert ui._talent_profile_window_singleton is replacement_profile
    assert ui._open_scene_dialogs[scene_id] is replacement_planner


def test_autosave_rotates_snapshots_without_reconnecting(window):
    controller = window.controller
    saves = window.save_manager
    engine = saves.db_manager.engine
    factory = controller.query_service.session_factory

    for _ in range(5):
        controller.advance_week()

    assert saves.db_manager.engine is engine
    assert saves.db_manager.get_session_factory() == factory
    for index, expected_week in enumerate((6, 5, 4, 3)):
        with closing(sqlite3.connect(saves.get_save_path(f"autosave_{index}"))) as database:
            saved_week, = database.execute("SELECT value FROM game_info WHERE key = 'absolute_week'").fetchone()
            assert int(saved_week) == expected_week
    assert len(saves.get_save_files()) == save_manager.AUTOSAVE_COUNT


def test_snapshot_includes_committed_wal_content(saves):
    with saves.replace_session() as candidate:
        with candidate.get_session() as session, session.begin():
            session.add(GameInfoDB(key="absolute_week", value="1"))

    path = saves.get_current_session_path()
    with closing(sqlite3.connect(path)) as database:
        assert database.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        database.execute("UPDATE game_info SET value = '2' WHERE key = 'absolute_week'")
        database.commit()
        assert Path(f"{path}-wal").exists()
        saves.save_game("WAL snapshot")

    with closing(sqlite3.connect(saves.get_save_path("WAL snapshot"))) as database:
        assert database.execute("SELECT value FROM game_info").fetchone() == ("2",)


def test_failed_exit_save_keeps_previous_save_and_leaves_game_open(window, monkeypatch):
    saves = window.save_manager
    window.show()
    window.controller.save_game(save_manager.EXITSAVE_NAME)
    exit_path = saves.get_save_path(save_manager.EXITSAVE_NAME)
    previous_save = exit_path.read_bytes()
    active_path = Path(saves.get_current_session_path())

    def fail_snapshot(_source, destination):
        destination.write_bytes(b"partial data")
        raise OSError("simulated disk failure")

    with monkeypatch.context() as patch:
        patch.setattr(saves, "_snapshot", fail_snapshot)
        assert not window.close()
    assert window.isVisible()
    assert Path(saves.get_current_session_path()) == active_path
    assert exit_path.read_bytes() == previous_save

    window.controller.advance_week()
    assert window.close()
    assert not active_path.exists()
    with closing(sqlite3.connect(exit_path)) as database:
        assert database.execute("SELECT value FROM game_info WHERE key = 'absolute_week'").fetchone() == ("2",)
