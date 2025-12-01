from PyQt6.QtWidgets import QTableView
from PyQt6.QtCore import pyqtSignal, QPoint
from ui.mixins.smart_hover_mixin import SmartHoverMixin

class SmartTableView(SmartHoverMixin, QTableView):
    """
    A QTableView that supports 'Smart Hover' and 'Alt+Click' interactions.
    It assumes the underlying model's UserRole data contains the entity object.
    """
    # Emits the object found in UserRole and the global mouse position
    smart_hover_entered = pyqtSignal(object, QPoint)
    smart_hover_left = pyqtSignal()
    # Emits the object found in UserRole
    smart_alt_clicked = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)