    
import os
import sys
from pathlib import Path

# Determine if the application is running as a bundled executable.
# Nuitka uses `__compiled__`, other tools (PyInstaller) use `sys.frozen`.
FROZEN = getattr(sys, 'frozen', False) or '__compiled__' in globals()
 
# --- Application Root (for read-only assets) ---
# This is the base directory from which we will look for 'assets' and 'data'.
if FROZEN:
    # In a bundled app, the application root is the directory of the executable.
    APP_ROOT = Path(sys.executable).parent
else:
    # In a development environment, this script is in 'src/utils', so we go
    # up three levels from this file to find the project root.
    # Path(.../src/utils/paths.py) -> .../src/utils -> .../src -> .../
    APP_ROOT = Path(__file__).resolve().parent.parent.parent
 
def resource_path(relative_path: str | Path) -> Path:
    """
    Get absolute path to a resource. Works for dev and packaged builds.
    For one-file builds (PyInstaller/Nuitka), resources are in a temporary folder.
    """
    if FROZEN and hasattr(sys, '_MEIPASS'):
        # This is the one-file build scenario. _MEIPASS is the path to the temp folder.
        base_path = Path(getattr(sys, '_MEIPASS'))
    else:
        # Development or one-folder build. Resources are relative to the app root.
        base_path = APP_ROOT
    
    return base_path / relative_path

# --- User Data Root (for writable files) ---
# It is best practice to store writable files (saves, logs, settings) in a
# user-specific directory, not next to the application executable. This avoids
# permission issues on systems where the app is installed in a protected location.
USER_DATA_ROOT = Path.home() / "PSM"

# --- Base directories for read-only assets and data ---
# These must use resource_path to handle being bundled inside an executable.
ASSETS_DIR = resource_path("assets")
DATA_DIR = resource_path("data")

# --- Base directories for writable files ---
# These are now in the user's home directory.
LOG_DIR = USER_DATA_ROOT / "logs"
SAVE_DIR = USER_DATA_ROOT / "saves"

# --- Create writable directories if they don't exist ---
LOG_DIR.mkdir(parents=True, exist_ok=True)
SAVE_DIR.mkdir(parents=True, exist_ok=True)

# Settings file (writable)
SETTINGS_FILE = USER_DATA_ROOT / "settings.json"

# Data sub-directories (read-only)
HELP_DIR = DATA_DIR / "help_content"
 
# Data files (read-only)
GAME_DATA = DATA_DIR / "game_data.sqlite"
HELP_FILE = DATA_DIR / "help_topics.json"
ACKNOWLEDGEMENTS_FILE = DATA_DIR / "acknowledgements.md"
 
# Log files (writable)
LOG_FILE = LOG_DIR / "app.log"
 
# Asset sub-directories and files (read-only)
IMG_DIR = ASSETS_DIR / "images"
FONTS_DIR = ASSETS_DIR / "fonts"
 
DISCORD_LOGO = IMG_DIR / "discord_icon.svg"
REDDIT_LOGO = IMG_DIR / "reddit_icon.svg"
GITHUB_LOGO = IMG_DIR / "github_icon.svg"

  