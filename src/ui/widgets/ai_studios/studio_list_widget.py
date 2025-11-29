from typing import List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QHeaderView
)
from PyQt6.QtCore import pyqtSignal, Qt
from ui.view_models import AIStudioViewModel

class StudioListWidget(QWidget):
    """
    Displays a list of AI Studios.
    Emits 'studio_selected(int)' when a row is clicked.
    """
    studio_selected = pyqtSignal(int)

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.theme = self.theme_manager.get_theme("light") # Default, updated by parent if needed
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Studio Name", "Location", "Funds"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        
        # Styling handled by global stylesheet usually, but we can set specific props
        self.tree.setAlternatingRowColors(True)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(self.tree)

    def set_studios(self, studios: List[AIStudioViewModel]):
        self.tree.clear()
        for studio in studios:
            item = QTreeWidgetItem([studio.name, studio.location, studio.money_str])
            item.setData(0, Qt.ItemDataRole.UserRole, studio.id)
            self.tree.addTopLevelItem(item)

    def _on_selection_changed(self):
        items = self.tree.selectedItems()
        if items:
            studio_id = items[0].data(0, Qt.ItemDataRole.UserRole)
            self.studio_selected.emit(studio_id)