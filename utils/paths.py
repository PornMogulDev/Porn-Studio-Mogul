import os
import sys

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # If not running as a PyInstaller bundle, use the project root directory
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # one level up from utils/

    return os.path.join(base_path, relative_path)

# Base directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # project root
ASSETS_DIR = resource_path("assets")
DATA_DIR = resource_path("data")
LOG_DIR = os.path.join(BASE_DIR, "logs")
SAVE_DIR = os.path.join(BASE_DIR, "saves") 

# Settings file
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

# Data files
GAME_DATA = os.path.join(DATA_DIR, "game_data.sqlite")
HELP_FILE = os.path.join(DATA_DIR, "help_topics.json")
ACKNOWLEDGEMENTS_TXT = os.path.join(DATA_DIR, "acknowledgements.txt")

# Logs files
LOG_FILE = os.path.join(LOG_DIR, "app.log")

# Asset sub-directories
IMG_DIR = os.path.join(ASSETS_DIR, "images")
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")

# Image paths
DISCORD_LOGO = os.path.join(IMG_DIR, "discord_icon.svg")
REDDIT_LOGO = os.path.join(IMG_DIR, "reddit_icon.svg")
GITHUB_LOGO = os.path.join(IMG_DIR, "github_icon.svg")

"""
GAME_CONSTANTS = os.path.join(DATA_DIR, "game_config.json")
GENERATOR_DATA = os.path.join(DATA_DIR, "talent_generation_data.json")
SCENE_TAGS = os.path.join(DATA_DIR, "scene_tags.json")
MARKET_DATA = os.path.join(DATA_DIR, "market.json")
COMPOSITION_RULES = os.path.join(DATA_DIR, "scene_composition_rules.json")
TALENT_AFFINITY_DATA = os.path.join(DATA_DIR, "talent_affinity_data.json")
"""