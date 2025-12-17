from PyQt6.QtWidgets import QTextBrowser
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QUrl
from PyQt6.QtGui import QDesktopServices

class SmartTextBrowser(QTextBrowser):
    """
    A specialized text browser for displaying email content.
    It intercepts links starting with 'talent:' to emit signals for hover/click handling,
    while allowing other links to open normally or be ignored.
    """
    # Signals
    smart_link_hover_entered = pyqtSignal(int, QPoint) # talent_id, global_pos
    smart_link_hover_left = pyqtSignal()
    smart_link_alt_clicked = pyqtSignal(int) # talent_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenExternalLinks(False) # We handle links manually
        self.setMouseTracking(True) # Required for hover detection
        self._last_hovered_talent_id = None

    def mouseMoveEvent(self, event):
        """
        Detects hover over anchors.
        """
        anchor_url = self.anchorAt(event.pos())
        
        if anchor_url:
            if anchor_url.startswith('talent:'):
                try:
                    talent_id = int(anchor_url.split(':')[1])
                    if talent_id != self._last_hovered_talent_id:
                        self._last_hovered_talent_id = talent_id
                        global_pos = self.mapToGlobal(event.pos())
                        self.smart_link_hover_entered.emit(talent_id, global_pos)
                except (ValueError, IndexError):
                    self._clear_hover()
            else:
                self._clear_hover()
        else:
            self._clear_hover()

        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        """
        Detects clicks on anchors.
        """
        anchor_url = self.anchorAt(event.pos())
        
        if anchor_url and anchor_url.startswith('talent:'):
            if event.modifiers() & Qt.KeyboardModifier.AltModifier:
                try:
                    talent_id = int(anchor_url.split(':')[1])
                    self.smart_link_alt_clicked.emit(talent_id)
                except (ValueError, IndexError):
                    pass
            # Consume the event so it doesn't try to navigate
            return
            
        super().mousePressEvent(event)

    def setSource(self, url: QUrl):
        # Override to prevent navigation if we click a talent link without alt
        if url.scheme() == 'talent':
            return
        super().setSource(url)

    def _clear_hover(self):
        if self._last_hovered_talent_id is not None:
            self.smart_link_hover_left.emit()
            self._last_hovered_talent_id = None