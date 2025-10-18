import os
import sys

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Adjusted: go up three levels to reach project root
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))

    return os.path.join(base_path, relative_path)

# Base directories
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
ASSETS_DIR = resource_path("assets")
DATA_DIR = resource_path("data")
LOG_DIR = os.path.join(BASE_DIR, "logs")
SAVE_DIR = os.path.join(BASE_DIR, "saves")

# Settings file
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

# Data sub-directories
EVENT_DIR = os.path.join(DATA_DIR, "events")
HELP_DIR = os.path.join(DATA_DIR, "help_content")
SCENE_SETTINGS_DIR = os.path.join(DATA_DIR, "scene_settings")
TAG_DIR = os.path.join(DATA_DIR, "tags")
TALENT_GEN_DIR = os.path.join(DATA_DIR, "talent_generation")

# Data files
GAME_DATA = os.path.join(DATA_DIR, "game_data.sqlite")
HELP_FILE = os.path.join(DATA_DIR, "help_topics.json")
ACKNOWLEDGEMENTS_TXT = os.path.join(DATA_DIR, "acknowledgements.txt")

# Log files
LOG_FILE = os.path.join(LOG_DIR, "app.log")

# Asset sub-directories
IMG_DIR = os.path.join(ASSETS_DIR, "images")
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")

# Image paths
DISCORD_LOGO = os.path.join(IMG_DIR, "discord_icon.svg")
REDDIT_LOGO = os.path.join(IMG_DIR, "reddit_icon.svg")
GITHUB_LOGO = os.path.join(IMG_DIR, "github_icon.svg")