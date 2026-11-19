# Game session replacement and cleanup

`SaveManager` owns the working SQLite database for the current game. It creates a private `.session-*` directory under the player’s saves directory for each working copy. Named saves, quicksaves, exit saves, and autosaves remain SQLite files in the saves directory.

## Starting or loading a game

1. `GameSessionService` asks `SaveManager.replace_session()` to prepare a candidate database in a separate directory. Loading copies the selected save through SQLite’s backup API and checks integrity, schema, and the saved week and studio state. A new game commits its initial state to the candidate.
2. Preparation failure removes the candidate and leaves the active database, services, and UI in use. After successful preparation, `session_changing` closes the previous game’s dialogs and clears session-specific filters and pending demand results.
3. `SaveManager` installs the candidate and retires the previous database. `GameController` initializes the services with the new session factory before emitting refresh signals. Worker inputs are captured when scheduled, and results carry a request ID so pending work from the previous game is ignored.

## Saving and ending a game

- SQLite’s backup API snapshots committed data, including committed WAL content, while the live SQLAlchemy engine stays open. Each named save is replaced after its snapshot succeeds. Autosaves prepare the new snapshot before rotating the four slots.
- Returning to the menu, quitting, or closing the application window saves first when the player requests an exit save. The window close button follows the `save_on_exit` setting. A failed exit save leaves the game open with its current session available.
- Cleanup clears the session-bound services, disconnects and disposes the session’s engine, and removes its private working directory. Retired factories reject new work. If the operating system still holds a file lock, the cleanup failure is logged and the next game uses its own directory.

Run `python -m pytest -q tests/test_session_lifecycle.py` for the save and session regression checks. [Production smoke check](../README.md#repeatable-development-game)
