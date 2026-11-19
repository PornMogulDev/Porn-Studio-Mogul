"""Launch a repeatable production scenario for development."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import random
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from utils.time_utils import from_absolute

if TYPE_CHECKING:
    from core.game_controller import GameController
    from data.game_state import Scene


SEED = 3218
START_SAVE = "Development Start"
RELEASE_SAVE = "Development Release"


def expect_scene(controller: GameController, scene_id: int, status: str) -> Scene:
    scene = controller.get_scene_by_id(scene_id)
    if scene is None or scene.status != status:
        actual = scene.status if scene else "missing"
        raise RuntimeError(f"Expected scene {scene_id} to be {status}, found {actual}.")
    return scene


def prepare_casting_scene(controller: GameController) -> Scene:
    controller.new_game_started()
    if controller.game_state is None:
        raise RuntimeError("Could not start the development game.")

    week = controller.game_state.absolute_week
    year, _ = from_absolute(week)
    builder = controller.get_shooting_bloc_builder()
    builder.set_num_scenes(1)
    if not controller.create_shooting_bloc(**builder.commit("Development Block", week)):
        raise RuntimeError("Could not create the development shooting block.")

    block, = controller.get_blocs_for_schedule_view(year)
    scene, = block.scenes
    expect_scene(controller, scene.id, "design")
    editor = controller.get_scene_state_editor(scene.id)
    if editor is None:
        raise RuntimeError("Could not open the development scene for editing.")

    editor.set_title("Development Scene")
    editor.update_performer_count(1)
    performer, = editor.working_scene.virtual_performers
    segment_id = editor.add_action_segment("Masturbation (Female)")
    if segment_id is None:
        raise RuntimeError("The development scene's action tag is missing. Rebuild the game data.")
    editor.update_action_segment_runtime(segment_id, 100)
    editor.update_slot_assignment(segment_id, "Masturbation_Performer_1", "Performer", performer.id)

    passed, message = editor.validate_and_set_status("Casting")
    if not passed:
        raise RuntimeError(message)
    controller.update_scene_full(editor.finalize_for_saving())
    scene = expect_scene(controller, scene.id, "casting")
    controller.save_game(START_SAVE)
    if not controller.save_manager.get_save_path(START_SAVE).is_file():
        raise RuntimeError("Could not save the development game's starting checkpoint.")
    return scene


def exercise_production_loop(controller: GameController, scene: Scene) -> None:
    scene_id = scene.id
    start_week = controller.game_state.absolute_week
    role, = scene.virtual_performers
    candidates = controller.get_eligible_talent_for_role(scene_id, role.id)
    if not candidates:
        raise RuntimeError("No eligible talent for the development scene.")
    talent_id = min(candidate.id for candidate in candidates)
    demands = controller.calculate_demands_for_multiple_talents([talent_id], scene_id, role.id)
    controller.cast_talent_for_virtual_performer(talent_id, scene_id, role.id, demands[talent_id])
    expect_scene(controller, scene_id, "scheduled")

    controller.advance_week()
    expect_scene(controller, scene_id, "shot")
    controller.start_editing_scene(scene_id, "quick_dirty")
    editing_scene = expect_scene(controller, scene_id, "in_editing")
    for _ in range(editing_scene.weeks_remaining):
        controller.advance_week()
    expect_scene(controller, scene_id, "ready_to_release")

    controller.release_scene(scene_id)
    released_scene = expect_scene(controller, scene_id, "released")
    controller.save_game(RELEASE_SAVE)

    controller.load_game(START_SAVE)
    expect_scene(controller, scene_id, "casting")
    if controller.game_state.absolute_week != start_week:
        raise RuntimeError("The casting checkpoint did not restore the starting week.")
    controller.load_game(RELEASE_SAVE)
    reloaded_scene = expect_scene(controller, scene_id, "released")
    if (
        reloaded_scene.revenue != released_scene.revenue
        or reloaded_scene.final_cast != released_scene.final_cast
    ):
        raise RuntimeError("The reloaded scene did not retain its revenue and cast.")


def run_game(smoke: bool) -> int:
    import numpy as np
    from PyQt6.QtWidgets import QApplication

    from app.application import ApplicationWindow
    from utils.paths import GAME_DATA

    if not GAME_DATA.is_file():
        raise SystemExit("Game data is missing. Run python data/scripts/migrate_to_sqlite.py first.")

    logging.basicConfig(level=logging.WARNING)
    app = QApplication([])
    window = ApplicationWindow()
    try:
        random.seed(SEED)
        np.random.seed(SEED)
        scene = prepare_casting_scene(window.controller)
        app.processEvents()
        if smoke:
            exercise_production_loop(window.controller, scene)
            print("Production smoke check passed through casting, release, and save/load.")
            return 0

        window.setWindowTitle("Porn Studio Mogul — Development Game")
        window.show()
        return app.exec()
    finally:
        window.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help="Run the production loop headlessly and exit.")
    args = parser.parse_args()

    # Talent generation iterates sets. Fix their order across development runs.
    if os.environ.get("PYTHONHASHSEED") != "0":
        return subprocess.call(
            [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
            env={**os.environ, "PYTHONHASHSEED": "0"},
        )

    with TemporaryDirectory(prefix="psm-dev-") as data_dir:
        os.environ["PSM_USER_DATA_DIR"] = data_dir
        if args.smoke:
            os.environ["QT_QPA_PLATFORM"] = "offscreen"
        return run_game(args.smoke)


if __name__ == "__main__":
    raise SystemExit(main())
