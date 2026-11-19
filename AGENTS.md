# Working on PSM

This directory is the Git root. Run commands here. Use the [README](README.md#run-from-source) to set up Python 3.12, install dependencies, and launch the game. The surrounding workspace may contain development logs and planning notes. The [in-game help](data/help_content/overview.md) also records design intent from earlier builds. Check the running code and tests for current behavior.

## Find the right place to change

| Task | Start here |
| --- | --- |
| Trace a player action | `src/ui/presenters/` → `src/core/game_controller.py` → `src/services/`. See the [request flows](docs/api_overview.md). |
| Wire a service or find its dependencies | [`ServiceContainer`](src/core/service_container.py) assembles the service graph. [`IGameController`](src/core/interfaces.py) describes the presenter-facing API. |
| Change a simulation rule | Look in `src/services/calculation/` and `src/services/models/` for the calculator and its inputs, configuration, and results. Rules and balancing data also live in `data/`. |
| Change scene editing or casting | Start with [`SceneStateEditor`](src/services/builders/scene_state_editor.py), then trace the presenter and the relevant scene or casting command. |
| Change save/load or turn advancement | Trace [`GameSessionService`](src/services/game_session_service.py), [`SaveManager`](src/data/save_manager.py), or [`TimeService`](src/services/time_service.py) from the controller. |

Keep Qt widgets focused on display and input, presenters on UI coordination, and game rules in the existing services and calculators. Reuse the established query, command, and builder paths so preview and commit use the same rules. Add dependencies through the service container and update the controller protocol when its public interface changes.

The operation that owns a database session owns its commit, rollback, and close. A helper that receives the caller's session participates in that transaction. Emit notifications of persisted changes after commit. If a change crosses a save, scene, or preset format boundary, check how existing data is read and round-tripped.

For modeless windows, check who owns the presenter and its signal connections. Use [`BasePresenter`](src/ui/presenters/base_presenter.py) and [`UIManager`](src/ui/managers/ui_manager.py) as the starting points for cleanup. When working with background calculations, pass the inputs needed for the calculation and check that a late result still belongs to the current session and view before applying it.

## Game data

Edit the tracked JSON inputs when changing static rules. Rebuild `data/game_data.sqlite` with `python data/scripts/migrate_to_sqlite.py` and check the success message before launching. The generated database is distinct from the live SQLite game session and player saves. If adding a new field, trace it through generation and loading as well as its consumer. Help topics and email templates are under `data/help_content/` and `data/email_templates/`.

## Verification

Start a bug fix from a concrete player action and expected outcome. The [workflow prompt](docs/ai_workflow_prompt.md) provides a checklist for implementation and review. Run the affected tests with `python -m pytest -q tests/<test_file>.py`. Add a focused regression test when the existing suite misses the behavior. Exercise the normal entry point for changes that involve a state transition, database round trip, or signal delivery. For generated scenarios, seed both Python's `random` and NumPy, or use explicit test data when exact values matter.

Run the full suite with `python -m pytest -q` after generating the game database. Pytest redirects player data to a temporary folder before collecting the tests. Report the checks and results. When a test and the code disagree about a game rule, look for the intended behavior in the design notes and adjacent tests before changing the expectation.

Use the [development game](README.md#repeatable-development-game) for the production loop. `python src/dev_game.py --smoke` checks the full path from design through release and save/load using the real services. `python src/dev_game.py` opens the same starting scenario for hands-on debugging.

For checks outside pytest or the development game, set `PSM_USER_DATA_DIR` to a scratch directory before importing application code or launching the game. Set `QT_QPA_PLATFORM=offscreen` when the check runs without a display.

For layout and theme changes, also record the platform and theme checked. Use headless Qt for widget behavior and check native geometry, styling, or packaged builds on the affected platform as applicable.

Keep changes scoped to the workflow being fixed. Update the closest documentation when a command, game rule, or cross-layer contract changes.
