import json
import os
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import gc  # <--- IMPORT GARBAGE COLLECTOR

from data.game_state import *
from database.db_manager import DBManager
from database.db_models import GameInfoDB
from utils.paths import SAVE_DIR

logger = logging.getLogger(__name__)

AUTOSAVE_NAME = "autosave"
QUICKSAVE_NAME = "quicksave"
EXITSAVE_NAME = "exitsave"
LIVE_SESSION_NAME = "session" # The name of the temporary DB file for the live game
AUTOSAVE_COUNT = 4

class SaveManager:
    """
    Manages game save/load operations and database file management.
    """
    def __init__(self):
        Path(SAVE_DIR).mkdir(exist_ok=True)
        self.db_manager = DBManager()
        self.cleanup_session_file()
    
    def get_current_session_path(self) -> Optional[str]:
        """Returns the path to the currently active database file, if any."""
        if self.db_manager:
            return self.db_manager.db_path
        return None

    def get_save_path(self, save_name: str) -> Path:
        return Path(SAVE_DIR) / f"{save_name}.sqlite"

    def create_new_save_db(self, save_name: str):
        """Creates a new, blank database file for a new game."""
        path = self.get_save_path(save_name)
        self.db_manager.create_database(str(path))
        return str(path)

    def copy_save(self, source_path: str, dest_save_name: str):
        """Copies the currently active DB file to a new named save."""
        if not source_path or not os.path.exists(source_path):
            logger.error(f"ERROR: Cannot copy save, source path '{source_path}' does not exist.")
            return
        dest_path = self.get_save_path(dest_save_name)
        try:
            shutil.copyfile(source_path, dest_path)
        except IOError as e:
            logger.error(f"Error copying save file: {e}")
    
    def auto_save(self):
        """Manages rolling autosaves and commits the current session."""
        
        # This disconnect is crucial on some systems to release the lock before copying
        live_db_path = self.db_manager.db_path
        self.db_manager.disconnect()
        
        self._manage_rolling_autosaves()
        
        # Copy the committed live DB to the new autosave_0 slot
        if live_db_path:
            self.copy_save(live_db_path, f"{AUTOSAVE_NAME}_0")

        # Reconnect to the live session file
        self.db_manager.connect_to_db(live_db_path)


    def _manage_rolling_autosaves(self):
        """Rotates existing autosave files."""
        autosave_files = sorted(Path(SAVE_DIR).glob(f"{AUTOSAVE_NAME}_*.sqlite"), 
                                key=lambda p: os.path.getmtime(p), reverse=True)

        # Rename older files
        for i in range(len(autosave_files) - 1, -1, -1):
            file_path = autosave_files[i]
            # Simple numeric rename based on position
            new_index = i + 1
            if new_index < AUTOSAVE_COUNT:
                new_path = self.get_save_path(f"{AUTOSAVE_NAME}_{new_index}")
                if new_path.exists(): new_path.unlink() # Avoid errors if target exists
                file_path.rename(new_path)
            else:
                # Delete the oldest if we exceed the count
                file_path.unlink()
    
    def load_game(self, save_name: str) -> GameState:
        """
        Copies the specified save DB to a temporary live session file,
        connects to it, and loads only the simple GameInfo.
        """
        source_path = self.get_save_path(save_name)
        if not source_path.exists():
            raise FileNotFoundError(f"Save file {source_path} not found")
        
        live_session_path = self.get_save_path(LIVE_SESSION_NAME)
        
        # Disconnect from any previous session before overwriting the file
        self.db_manager.disconnect()
        
        # Copy the selected save to be the new live session
        shutil.copyfile(source_path, live_session_path)

        self.db_manager.connect_to_db(str(live_session_path))
        session = self.db_manager.get_session()
        
        game_info = {row.key: row.value for row in session.query(GameInfoDB).all()}
        session.close()

        # Create a minimal GameState object. Large dicts are intentionally empty.
        state = GameState(
            week=int(game_info.get('week', 1)),
            year=int(game_info.get('year', 0)),
            money=int(game_info.get('money', 0)),
            studio_location=str(game_info.get('studio_location'))
        )
        return state

    def load_latest_save(self) -> Optional[str]:
        # Exclude the live session file from being considered the "latest save"
        save_files = [sf for sf in self.get_save_files() if sf['name'] != LIVE_SESSION_NAME]
        if not save_files: return None
        return save_files[0]['name']

    def quick_load_exists(self) -> bool:
        return self.get_save_path(QUICKSAVE_NAME).exists()

    def has_saves(self) -> bool:
        # Check for any save file that isn't the live session file
        return any(p.stem != LIVE_SESSION_NAME for p in Path(SAVE_DIR).glob("*.sqlite"))

    def delete_save(self, save_name: str) -> bool:
        path = self.get_save_path(save_name)
        if path.exists():
            try:
                path.unlink()
                return True
            except OSError as e:
                logger.error(f"Error deleting save file {path}: {e}")
                return False
        return False
    
    def get_save_files(self) -> List[Dict]:
        saves = []
        for file in Path(SAVE_DIR).glob("*.sqlite"):
            # Do not show the internal session file to the player
            if file.stem == LIVE_SESSION_NAME:
                continue
            stats = file.stat()
            saves.append({
                'name': file.stem,
                'path': str(file),
                'date': datetime.fromtimestamp(stats.st_mtime),
                'size': stats.st_size
            })
        return sorted(saves, key=lambda x: x['date'], reverse=True)
    
    def cleanup_session_file(self):
        """Deletes the temporary live session database file if it exists.
        This method is the single point of truth for session cleanup. It
        disconnects the database and then attempts to delete the file with
        retries to handle OS-level file locking delays.
        """
        import time
        
        session_path = self.get_save_path(LIVE_SESSION_NAME)
        if not session_path.exists():
            logger.debug("cleanup_session_file called, but no session.sqlite exists. Nothing to do.")
            return

        logger.info(f"Attempting to clean up session file: {session_path}")

        # 1. Disconnect from the database and release all file handles.
        # This is the most critical step. We nullify the DBManager, which holds
        # the SQLAlchemy engine and connection pool, and then explicitly call
        # the garbage collector. This is the most reliable way to force the
        # release of the underlying file handle on Windows.
        if self.db_manager:
            logger.debug("Disconnecting and destroying DBManager instance to release file lock...")
            self.db_manager.disconnect()
            self.db_manager = None # Encourage garbage collection
            logger.debug("Forcing garbage collection to release file handles...")
            gc.collect() # <--- FORCE garbage collection

        # 2. Add a small, initial delay. This is crucial on Windows to give
        # the OS time to actually release the file handle after disconnect.
        logger.debug("Waiting 100ms for OS to release file handle...")
        time.sleep(0.1)

        # 3. Retry deleting the file with increasing backoff.
        max_retries = 5
        retry_delay = 0.1
        deleted = False

        for attempt in range(max_retries):            
            try:
                session_path.unlink()
                logger.info("Successfully deleted session.sqlite.")
                deleted = True
                break # Exit the loop on success

            except PermissionError:
                if attempt < max_retries - 1:
                    logger.warning(f"Attempt {attempt + 1}/{max_retries} to delete session.sqlite failed (PermissionError). Retrying...")
                    time.sleep(retry_delay * (2 ** attempt)) # Exponential backoff
                else:
                    logger.error(f"Could not delete session.sqlite after {max_retries} attempts. File remains locked.")
            except Exception as e:
                logger.error(f"Unexpected error cleaning up session file: {e}", exc_info=True)
                break # Exit loop on other errors

        if not deleted:
            logger.error(
                f"FATAL: Could not delete session.sqlite after {max_retries} attempts. "
                "File is locked. The application may be unstable on next new game."
            )

        # 4. Re-initialize the DBManager for future operations (e.g., starting a new game).
        logger.debug("Re-initializing DBManager for future use.")
        self.db_manager = DBManager()