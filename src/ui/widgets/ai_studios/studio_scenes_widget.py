from typing import List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QLabel
)
from PyQt6.QtCore import Qt
from ui.view_models import AISceneViewModel

class StudioScenesWidget(QWidget):
    """
    Displays a table of scenes produced by the selected AI Studio.
    """
    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.title_label = QLabel("Studio Filmography")
        # Apply header styling via object name if needed, or theme logic
        font = self.title_label.font()
        font.setBold(True)
        self.title_label.setFont(font)
        layout.addWidget(self.title_label)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Title", "Released", "Orient/Dyn", "Tags", "Market", "Revenue"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # Title
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch) # Tags gets the space
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        layout.addWidget(self.table)

    def set_scenes(self, scenes: List[AISceneViewModel]):
        self.table.setRowCount(len(scenes))
        for row, scene in enumerate(scenes):
            self.table.setItem(row, 0, QTableWidgetItem(scene.title))
            self.table.setItem(row, 1, QTableWidgetItem(scene.date_str))
            # Combined Orientation + Dynamic
            self.table.setItem(row, 2, QTableWidgetItem(f"{scene.orientation} ({scene.dynamic_level_str})"))
            
            # Tags
            tags_item = QTableWidgetItem(scene.tags_str)
            tags_item.setToolTip(scene.tags_str) # Tooltip for long lists
            self.table.setItem(row, 3, tags_item)
            
            self.table.setItem(row, 4, QTableWidgetItem(scene.market_group))
            self.table.setItem(row, 5, QTableWidgetItem(scene.revenue_str))

    def clear(self):
        self.table.setRowCount(0)