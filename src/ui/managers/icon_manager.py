from pathlib import Path
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtCore import QByteArray, QSize, Qt
from PyQt6.QtSvg import QSvgRenderer

from utils.paths import ICON_DIR
from ui.managers.theme_manager import ThemeManager

class IconManager:
    """
    Manages loading, caching, and recoloring of UI icons.
    """
    def __init__(self, theme_manager: ThemeManager):
        self.theme_manager = theme_manager
        self._cache = {}
        
        # Determine current theme colors
        # We grab the current theme to determine default icon colors
        theme = self.theme_manager.get_theme(self.theme_manager.settings_manager.get_setting("theme", "light"))
        self.current_text_color = theme.text
        self.current_accent_color = theme.accent

    def get_icon(self, name: str, color: str = None) -> QIcon:
        """
        Loads an SVG icon, optionally recoloring it.
        
        Args:
            name: The filename without extension (e.g., "lock_open").
            color: Hex code (e.g., "#FFFFFF") or None to use the theme's text color.
        """
        # 1. Determine Color
        if color is None:
            color = self.current_text_color

        # 2. Check Cache
        cache_key = f"{name}_{color}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 3. Locate File (Support .svg or .png, prefer .svg)
        file_path = ICON_DIR / f"{name}.svg"
        if not file_path.exists():
            file_path = ICON_DIR / f"{name}.png"
            if not file_path.exists():
                # Return empty icon if not found
                return QIcon()

        # 4. Process SVG (Recolor) or Load PNG
        if file_path.suffix == ".svg":
            icon = self._load_colored_svg(file_path, color)
        else:
            icon = QIcon(str(file_path))

        # 5. Cache and Return
        self._cache[cache_key] = icon
        return icon

    def _load_colored_svg(self, file_path: Path, color_hex: str) -> QIcon:
        """
        Reads SVG data, renders it to a QPixmap with the specific color applied 
        (assuming the SVG uses specific rules or we simple-mask it).
        
        For robust recoloring, we read the XML and replace 'fill' attributes, 
        or use a QPainter composition mode.
        """
        # Approach: Render SVG to Pixmap, then use QPainter to colorize non-transparent pixels.
        # This works for monochrome icons, which UI icons usually are.
        
        renderer = QSvgRenderer(str(file_path))
        if not renderer.isValid():
            return QIcon()
            
        # Standard icon size for rendering resolution (high enough for high-DPI)
        base_size = QSize(64, 64) 
        pixmap = QPixmap(base_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        renderer.render(painter)
        
        # Composition: SourceIn keeps the alpha of the destination (the SVG shape)
        # but fills it with the source (the color we want).
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(color_hex))
        painter.end()
        
        return QIcon(pixmap)

    def refresh_theme(self):
        """Called when theme changes to clear cache and update default colors."""
        theme = self.theme_manager.get_theme(self.theme_manager.settings_manager.get_setting("theme", "light"))
        self.current_text_color = theme.text
        self.current_accent_color = theme.accent
        self._cache.clear()