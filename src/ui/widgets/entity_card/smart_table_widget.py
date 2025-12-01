from PyQt6.QtWidgets import QTableWidget
from PyQt6.QtCore import pyqtSignal, QPoint
from ui.mixins.smart_hover_mixin import SmartHoverMixin

class SmartTableWidget(SmartHoverMixin, QTableWidget):
    """
    A QTableWidget that supports 'Smart Hover' and 'Alt+Click' interactions.
    It assumes the item's UserRole data contains the entity ID or Object.
    """
    # Emits the data found in UserRole and the global mouse position
    smart_hover_entered = pyqtSignal(object, QPoint)
    smart_hover_left = pyqtSignal()
    # Emits the data found in UserRole
    smart_alt_clicked = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)