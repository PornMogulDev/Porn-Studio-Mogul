import json
import os
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

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
    
    SESSION MANAGEMENT PATTERN: File Operations (No Session Required)
    ==================================================================
    
    Architecture:
    -------------
    This service performs file-level operations on SQLite database files.
    It does NOT need sessions for file copying/moving operations, but uses
    temporary sessions for initialization and metadata reading.
    
    Key Principles:
    ---------------
    1. File operations (copy/move/delete) do NOT require sessions
    2. Disconnect from database before file operations to release locks
    3. Reconnect after file operations for future use
    4. Use temporary sessions for initialization only
    5. Assume all changes are committed before calling file operations
    
    Pattern 1: File Operations (autosave, quicksave, copy)
    ------------------------------------------------------
    def file_operation(self):
        '''Operations on database files.'''
        # Get the path (no session needed)
        db_path = self.db_manager.db_path
        
        # Disconnect to release file locks
        self.db_manager.disconnect()
        
        try:
            # Perform file operations (copy, move, delete)
            shutil.copyfile(source, destination)
        finally:
            # Reconnect for future operations
            self.db_manager.connect_to_db(db_path)
    
    Pattern 2: Initialization with Temporary Session
    -------------------------------------------------
    def load_game(self, save_name: str) -> GameState:
        '''Load metadata from save file.'''
        # Copy file (no session)
        shutil.copyfile(source, destination)
        
        # Connect and create temporary session
        self.db_manager.connect_to_db(destination)
        session = self.db_manager.get_session()
        
        try:
            # Read metadata
            game_info = session.query(GameInfoDB).all()
            # Process data
            state = GameState(...)
        finally:
            session.close()  # Close temporary session
        
        # Services will create their own sessions later
        return state
    
    Autosave Integration with Session Factory Pattern:
    --------------------------------------------------
    The autosave() method works seamlessly with the new pattern:
    
    1. TimeService.advance_week() creates session, commits, closes
    2. GameController.advance_week() calls save_manager.auto_save()
    3. auto_save() assumes database is already committed
    4. auto_save() disconnects, copies file, reconnects
    5. No session parameter needed!
    
    Old Pattern (broken):
    ---------------------
    def advance_week(self):
        result = self.time_service.advance_week()
        self.save_manager.auto_save(session)  # ❌ What session?
    
    New Pattern (correct):
    ----------------------
    def advance_week(self):
        # TimeService commits and closes its session internally
        result = self.time_service.advance_week()
        
        # auto_save just copies the committed database file
        self.save_manager.auto_save()  # ✅ No session needed!
    
    Benefits:
    ---------
    - Clear separation: file operations vs database operations
    - No session confusion: file ops don't need sessions
    - Lock safety: disconnect before file operations
    - Works with session factory: assumes committed state
    """
    def __init__(self):
        Path(SAVE_DIR).mkdir(exist_ok=True)
        self.db_manager = DBManager()
        self.cleanup_session_file()

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
            money=int(game_info.get('money', 0))
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
        """Deletes the temporary live session database file if it exists."""
        session_path = self.get_save_path(LIVE_SESSION_NAME)
        if session_path.exists():
            self.db_manager.disconnect() # Ensure no locks are held
            session_path.unlink()
            logger.info("Cleaned up stale session.sqlite file.")