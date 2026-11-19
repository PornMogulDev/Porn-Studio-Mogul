import logging
import shutil
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory, mkdtemp
from typing import Iterator

from database.db_manager import DBManager
from utils.paths import SAVE_DIR

logger = logging.getLogger(__name__)

AUTOSAVE_NAME = "autosave"
QUICKSAVE_NAME = "quicksave"
EXITSAVE_NAME = "exitsave"
LIVE_SESSION_NAME = "session"
AUTOSAVE_COUNT = 4
SESSION_DIRECTORY_PREFIX = ".session-"


class SaveManager:
    """Owns the working database and snapshots of committed game state."""

    def __init__(self):
        self.save_dir = Path(SAVE_DIR).resolve()
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.db_manager = DBManager()

    def get_current_session_path(self) -> str | None:
        return self.db_manager.db_path

    def get_save_path(self, save_name: str) -> Path:
        filename = f"{save_name}.sqlite"
        if not save_name or Path(filename).name != filename or save_name.casefold() == LIVE_SESSION_NAME:
            raise ValueError(f"Invalid save name: {save_name!r}")
        return self.save_dir / filename

    @contextmanager
    def replace_session(self, save_name: str | None = None) -> Iterator[DBManager]:
        """Install a candidate database only after the caller prepares and validates it."""
        source = self.get_save_path(save_name) if save_name is not None else None
        if source is not None and not source.is_file():
            raise FileNotFoundError(source)

        workspace = Path(mkdtemp(prefix=SESSION_DIRECTORY_PREFIX, dir=self.save_dir))
        path = workspace / f"{LIVE_SESSION_NAME}.sqlite"
        candidate = DBManager()
        try:
            if source is not None:
                self._snapshot(source, path)
            candidate.connect_to_db(str(path))
            if source is not None:
                candidate.validate_database()
            yield candidate
        except BaseException:
            candidate.disconnect()
            self._remove_workspace(workspace)
            raise

        previous = self.db_manager
        self.db_manager = candidate
        self._discard_session(previous)

    @staticmethod
    def _snapshot(source: Path, destination: Path):
        uri = source.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as reader:
            with closing(sqlite3.connect(destination)) as writer:
                reader.backup(writer)

    def save_game(self, save_name: str):
        """Write the snapshot beside the destination, then replace the save atomically."""
        destination = self.get_save_path(save_name)
        source = self._active_path()
        with TemporaryDirectory(prefix=".save-", dir=self.save_dir) as directory:
            snapshot = Path(directory) / "snapshot.sqlite"
            self._snapshot(source, snapshot)
            snapshot.replace(destination)

    def auto_save(self):
        """Rotate the autosave slots after a new snapshot is ready."""
        source = self._active_path()
        latest = self.get_save_path(f"{AUTOSAVE_NAME}_0")
        with TemporaryDirectory(prefix=".save-", dir=self.save_dir) as directory:
            snapshot = Path(directory) / "snapshot.sqlite"
            self._snapshot(source, snapshot)

            for index in range(AUTOSAVE_COUNT - 1, 1, -1):
                previous = self.get_save_path(f"{AUTOSAVE_NAME}_{index - 1}")
                if previous.exists():
                    previous.replace(self.get_save_path(f"{AUTOSAVE_NAME}_{index}"))
            if latest.exists():
                # Preserve the latest save if installing the new snapshot fails.
                archive = Path(directory) / "archive.sqlite"
                shutil.copy2(latest, archive)
                archive.replace(self.get_save_path(f"{AUTOSAVE_NAME}_1"))
            snapshot.replace(latest)

    def _active_path(self) -> Path:
        path = self.get_current_session_path()
        if path is None:
            raise ConnectionError("No active game to save.")
        return Path(path)

    def load_latest_save(self) -> str | None:
        saves = self.get_save_files()
        return saves[0]["name"] if saves else None

    def quick_load_exists(self) -> bool:
        return self.get_save_path(QUICKSAVE_NAME).is_file()

    def has_saves(self) -> bool:
        return any(path.is_file() and path.stem.casefold() != LIVE_SESSION_NAME
                   for path in self.save_dir.glob("*.sqlite"))

    def delete_save(self, save_name: str) -> bool:
        try:
            self.get_save_path(save_name).unlink()
            return True
        except FileNotFoundError:
            return False
        except (OSError, ValueError):
            logger.exception("Could not delete save %r", save_name)
            return False

    def get_save_files(self) -> list[dict]:
        saves = []
        for file in self.save_dir.glob("*.sqlite"):
            # Older versions used a sibling session.sqlite file for live state.
            if file.stem.casefold() == LIVE_SESSION_NAME or not file.is_file():
                continue
            stats = file.stat()
            saves.append({
                "name": file.stem,
                "path": str(file),
                "date": datetime.fromtimestamp(stats.st_mtime),
                "size": stats.st_size,
            })
        return sorted(saves, key=lambda save: save["date"], reverse=True)

    def cleanup_session_file(self):
        self._discard_session(self.db_manager)

    def _discard_session(self, manager: DBManager):
        path = manager.db_path
        manager.disconnect()
        if path is not None:
            workspace = Path(path).parent
            if workspace.parent == self.save_dir and workspace.name.startswith(SESSION_DIRECTORY_PREFIX):
                self._remove_workspace(workspace)

    @staticmethod
    def _remove_workspace(workspace: Path):
        try:
            shutil.rmtree(workspace)
        except FileNotFoundError:
            pass
        except OSError:
            logger.warning("Could not remove retired game workspace %s", workspace, exc_info=True)
