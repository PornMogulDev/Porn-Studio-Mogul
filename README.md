# Porn Studio Mogul

Porn Studio Mogul (PSM) is a turn-based desktop management game about running an adult-film studio. You design scenes, cast talent, budget and schedule shooting blocks, then edit and release the finished scenes. Talent preferences, fatigue, availability, and travel affect who you can book. Audience tastes and rival studio releases shape the market you sell into.

The game is in active development. The in-game Help covers the main workflows and includes design notes from earlier builds.

## Run from source

Use Python 3.12, the version used for the current development checks. Run these commands from the Git checkout root, the directory containing `src/`, `data/`, and `requirements.txt`.

Create and activate a virtual environment.

**Linux or macOS shell**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

**Windows PowerShell**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the dependencies, build the static game database, and launch the game.

```sh
python -m pip install -r requirements.txt
python data/scripts/migrate_to_sqlite.py
python src/main.py
```

The generator builds `data/game_data.sqlite` from the tracked JSON files. Check for its `Migration completed successfully!` message. The generated file is Git-ignored. Rebuild it after pulling or editing the data that feeds it. Each rebuild replaces the generated database.

The game keeps saves, settings, and logs in `PSM Saves & Config` under your user Documents folder, with your home folder as the fallback. [User data paths](src/utils/paths.py)

## Repeatable development game

After building the game data, run `python src/dev_game.py` to open a seeded game with **Development Scene** already in Casting in **Development Block**. Use it to try hiring, shooting, editing, and releasing from a known starting point. The **Development Start** save is available during the run. Each launch uses a fresh temporary folder for player data, which is removed on exit.

Run `python src/dev_game.py --smoke` to exercise the same scenario through release and save/load headlessly. Reproduce a run with the same generated game data and Python dependencies.

## Run the tests

From the same environment, install pytest and run the suite.

```sh
python -m pip install pytest==8.4.2
python -m pytest -q
```

The initial audit found existing failures in the shoot-result fixtures and market/revenue tests. Run `python -m pytest -q tests/test_production_smoke.py` to check the development scenario alone. See [AGENTS.md](AGENTS.md#verification) for guidance on verifying changes.

## Contributing

For a bug report, include the build or commit, operating system, steps to reproduce, and what you expected to happen. If a save or preset is needed to reproduce it, note which version created it.

For a code change, start with the [request flows](docs/api_overview.md) and the [service architecture guide](docs/SERVICE_ARCHITECTURE.md). The [project structure guide](docs/project_structure.md) helps locate components. [AGENTS.md](AGENTS.md) describes the conventions for changes and checks.

## License and credits

See the [GNU GPL v3 license](LICENSE.txt), [acknowledgements](acknowledgements.md), [asset notices](NOTICE.md), and [third-party licenses](THIRD_PARTY_LICENSES.md).
