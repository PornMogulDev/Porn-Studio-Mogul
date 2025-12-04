from pathlib import Path
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction
from PyQt6.QtCore import QSize, Qt, QObject
from PyQt6.QtWidgets import QAbstractButton 
from PyQt6.QtSvg import QSvgRenderer

from data.settings_manager import SettingsManager
from utils.paths import ICON_DIR, FLAG_DIR
from ui.managers.theme_manager import ThemeManager, Theme

class IconManager:
    """
    Manages loading, caching, and recoloring of UI icons based on Semantic Roles.
    """
    
    # Mapping of "String Role" -> "Theme.attribute_name"
    ROLE_MAP = {
        # Core
        "text": "text",
        "primary": "text",
        "accent": "accent",
        "accent_hover": "accent_hover",
        
        # States
        "disabled": "disabled_text",
        "success": "color_good",
        "warning": "color_warning",
        "error": "color_bad",
        "danger": "danger",
        "neutral": "color_neutral",
        
        # Specifics
        "unread": "color_warning",
        "locked": "disabled_text", # Visual preference for locks
    }

    # Map Game Strings -> ISO Codes (Filenames)
    NATIONALITY_MAP = {
        "US": "us",
        "Japanese": "jp",
        "French": "fr",
        "Belgian": "be",
        "German": "de",
        "British": "gb",
        "Brazilian": "br",
        "Russian": "ru",
        "Ukrainian": "ua",
        "Belarusian": "by",
        "Canadian": "ca",
        "Mexican": "mx",
        "Australian": "au",
        "Colombian": "co",
        "Venezuelan": "ve",
        "Argentinian": "ar",
        "Czech": "cz",
        "Hungarian": "hu",
        "Spanish": "es",
        "Italian": "it",
        "Polish": "pl",
        "Moldovan": "md",
        "Romanian": "ro",
        "Dutch": "nl",
        "Latvian": "lv"
    }

    def __init__(self, theme_manager: ThemeManager, settings_manager: SettingsManager):
        self.theme_manager = theme_manager
        self.settings_manager = settings_manager
        self._cache = {}
        self._current_theme_obj = None
        self.refresh_theme()

        self.settings_manager.signals.setting_changed.connect(self._on_setting_changed)

    def _on_setting_changed(self, key: str):
        if key == "font_size":
            self._cache.clear()

    @property
    def current_theme(self) -> Theme:
        return self._current_theme_obj

    def get_icon(self, name: str, role: str = "text") -> QIcon:
        """
        Returns an icon colored according to the semantic role.
        
        Args:
            name: Filename without extension.
            role: Semantic key (e.g., 'warning', 'disabled') OR a hex code.
        """
        # 1. Resolve Color from Role
        color_hex = self._resolve_color(role)

        # 2. Check Cache
        cache_key = f"{name}_{color_hex}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 3. Load & Colorize
        icon = self._load_icon_from_disk(name, color_hex)
        
        # 4. Cache
        self._cache[cache_key] = icon
        return icon
    
    def get_target_size(self) -> QSize:
        """Calculates a square icon size based on the current font size."""
        font_size = self.settings_manager.font_size
        # Multiplier to ensure icons are large enough relative to text (e.g., 12pt -> 24px)
        size = int(font_size * 2.0)
        return QSize(size, size)

    def apply_icon(self, target: QObject, icon_name: str, role: str = None):
        """
        QT STYLE HELPER:
        Resolves the color based on the role and sets the icon on the target.
        If 'role' is provided, it updates the 'iconRole' property on the target as well.
        If 'role' is not provided, it attempts to read 'iconRole' from the target.
        
        Usage:
            icon_manager.apply_icon(btn, "alert", "warning")
        """
        if role:
            target.setProperty("iconRole", role)
        else:
            role = target.property("iconRole")
        if not role:
            role = "text" # Default
            
        icon = self.get_icon(icon_name, role)
        
        if isinstance(target, (QAbstractButton, QAction)):
            target.setIcon(icon)
            if isinstance(target, QAbstractButton):
                target.setIconSize(self.get_target_size())

    def _resolve_color(self, role: str) -> str:
        """Helper to convert role string to hex color."""
        # A. Is it a mapped role?
        if role in self.ROLE_MAP:
            attr_name = self.ROLE_MAP[role]
            return getattr(self._current_theme_obj, attr_name, "#FF00FF")
            
        # B. Is it a direct Theme attribute? (e.g. "accent_text")
        if hasattr(self._current_theme_obj, role):
            return getattr(self._current_theme_obj, role)

        # C. Assume it's a raw hex code
        return role

    def _load_icon_from_disk(self, name: str, color_hex: str) -> QIcon:
        file_path = ICON_DIR / f"{name}.svg"
        if not file_path.exists():
            file_path = ICON_DIR / f"{name}.png"
            if not file_path.exists():
                return QIcon()

        if file_path.suffix == ".svg":
            return self._colorize_svg(file_path, color_hex)
        else:
            return QIcon(str(file_path))

    def _colorize_svg(self, file_path: Path, color_hex: str) -> QIcon:
        renderer = QSvgRenderer(str(file_path))
        if not renderer.isValid():
            return QIcon()
            
        base_size = self.get_target_size() 
        pixmap = QPixmap(base_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(color_hex))
        painter.end()
        
        return QIcon(pixmap)

    def refresh_theme(self):
        theme_name = self.theme_manager.settings_manager.get_setting("theme", "light")
        self._current_theme_obj = self.theme_manager.get_theme(theme_name)
        self._cache.clear()

    def get_flag_icon(self, nationality: str) -> QIcon:
        """
        Retrieves the flag icon for a given nationality string.
        """
        # 1. Check Cache first (using a prefix to avoid collision with generic icons)
        cache_key = f"flag_{nationality}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 2. Lookup the ISO code
        iso_code = self.NATIONALITY_MAP.get(nationality)
        
        # 3. Fallback logic
        if not iso_code:
            iso_code = nationality.lower()

        file_name = f"{iso_code}.svg"
        file_path = FLAG_DIR / file_name
        
        icon = None
        
        # 4. Load
        if file_path.exists():
             icon = self._load_original_svg(file_path)
        else:
            # Fallback to generic globe, but we must cache this result too
            # so we don't check disk for missing flags repeatedly.
            icon = self.get_icon("globe_icon", "neutral") 

        # 5. Cache and return
        self._cache[cache_key] = icon
        return icon

    def _load_original_svg(self, file_path: Path) -> QIcon:
        """Loads SVG directly without recoloring."""
        return QIcon(str(file_path))