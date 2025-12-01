from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor

class SmartLabel(QLabel):
    """
    A clickable, hoverable label representing a link to an entity (Talent).
    code Code

        
    Interactions:
    - Hover: Emits signal to show summary card.
    - Leave: Emits signal to hide summary card.
    - Alt + Left Click: Emits signal to open full profile.
    """
    # Signals to be connected to the UIManager
    profile_requested = pyqtSignal(int)      # Emits talent_id
    hover_entered = pyqtSignal(int, object)  # Emits talent_id, global_pos (QPoint)
    hover_left = pyqtSignal()

    def __init__(self, text: str, talent_id: int, parent=None):
        super().__init__(text, parent)
        self.talent_id = talent_id
        
        # Visual cues
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # This property allows theme_manager to target this specific type of label
        self.setProperty("role", "smart_link")

    def enterEvent(self, event):
        # Map local mouse position to global screen position for the tooltip
        global_pos = self.mapToGlobal(event.position().toPoint())
        self.hover_entered.emit(self.talent_id, global_pos)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hover_left.emit()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Only trigger profile open on Alt + Click as requested
            if event.modifiers() & Qt.KeyboardModifier.AltModifier:
                self.profile_requested.emit(self.talent_id)
        super().mousePressEvent(event)