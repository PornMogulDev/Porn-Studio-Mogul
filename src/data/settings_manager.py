import json
import os
import logging
from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QFont, QFontDatabase

from utils.paths import SETTINGS_FILE, FONTS_DIR

logger = logging.getLogger(__name__)

class SettingsSignals(QObject):
    """Container for signals related to settings changes."""
    # The string argument will be the key of the setting that changed
    setting_changed = pyqtSignal(str)

class SettingsManager:
    """
    Manages loading, saving, and accessing application settings.
    This class is designed as a singleton pattern.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SettingsManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.signals = SettingsSignals()
        for font_file in [
        "Roboto-VariableFont_wdth,wght.ttf",
        "Roboto-Italic-VariableFont_wdth,wght.ttf"
    ]:
            font_path = os.path.join(FONTS_DIR, font_file)
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id == -1:
                logger.error(f"Failed to load {font_path}")

        self._default_settings = {
            "save_on_exit": True,
            "unit_system": "imperial",  # 'imperial' or 'metric'
            "window_geometries": {},
            "theme": "system",  # 'dark', 'light', or 'system'
            "font_family": "Roboto",
            "font_size": 12,
            "talent_profile_dialog_behavior": "singleton"  # 'singleton' or 'multiple'
        }
        self.settings = self._load_settings()

    @property
    def font_family(self) -> str:
        return self.get_setting("font_family", "Roboto")

    @property
    def font_size(self) -> int:
        return self.get_setting("font_size", 12)

    def get_app_font(self) -> QFont:
        """Creates a QFont object from the current settings."""
        return QFont(self.font_family, self.font_size)



    def _load_settings(self) -> dict:
        """Loads settings from the JSON file, merging with defaults."""
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    loaded_settings = json.load(f)
                # Merge loaded settings with defaults to ensure new settings are added
                # and old settings are preserved.
                settings = self._default_settings.copy()
                settings.update(loaded_settings)
                return settings
            except json.JSONDecodeError:
                logger.warning(f"Warning: Could not decode {SETTINGS_FILE}. Using default settings.")
                return self._default_settings.copy()
        return self._default_settings.copy()

    def _save_settings(self):
        """Saves the current settings to the JSON file."""
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except IOError as e:
            logger.error(f"Error: Could not save settings to {SETTINGS_FILE}: {e}")

    def get_setting(self, key: str, default=None):
        """Retrieves a setting value by its key."""
        return self.settings.get(key, default)

    def set_setting(self, key: str, value):
        """Sets a setting value, saves it, and emits a signal."""
        if self.settings.get(key) != value:
            self.settings[key] = value
            self._save_settings()
            self.signals.setting_changed.emit(key)

    def get_window_geometry(self, window_name: str) -> Optional[dict]:
        """
        Retrieves the saved geometry (x, y, width, height) for a window.
        
        Args:
            window_name: The unique identifier for the window (e.g., its class name).
            
        Returns:
            A dictionary with geometry data, or None if not found.
        """
        return self.settings.get("window_geometries", {}).get(window_name)

    def set_window_geometry(self, window_name: str, geometry: dict):
        """
        Saves the geometry for a specific window.
        
        Args:
            window_name: The unique identifier for the window.
            geometry: A dictionary containing keys for 'x', 'y', 'width', 'height'.
        """
        if "window_geometries" not in self.settings:
            self.settings["window_geometries"] = {}
        self.settings["window_geometries"][window_name] = geometry
        self._save_settings()

    def clear_all_window_geometries(self):
        """
        Resets all saved window geometry data, effectively reverting them to default.
        """
        if "window_geometries" in self.settings:
            self.settings["window_geometries"] = {}
            self._save_settings()
            self.signals.setting_changed.emit("window_geometries")