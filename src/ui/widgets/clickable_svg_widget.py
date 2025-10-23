from pathlib import Path
from PyQt6.QtCore import QSize, Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QSizePolicy
from PyQt6.QtSvgWidgets import QSvgWidget

class ClickableSvgWidget(QSvgWidget):
    """A simplified, layout-friendly SVG widget that maintains its aspect ratio."""
    def __init__(self, svg_file: str | Path, url: str):
        if isinstance(svg_file, Path):
            super().__init__(str(svg_file))
        else:
            super().__init__(svg_file)
        self.url = url
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.renderer = self.renderer()
        if self.renderer.defaultSize().width() > 0:
            self.aspect_ratio = self.renderer.defaultSize().height() / self.renderer.defaultSize().width()
        else:
            self.aspect_ratio = 1.0  # Fallback for invalid SVGs

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumSize(50, int(50 * self.aspect_ratio))
        self.setMaximumSize(280, int(280 * self.aspect_ratio))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return int(width * self.aspect_ratio)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            QDesktopServices.openUrl(QUrl(self.url))
        super().mousePressEvent(event)