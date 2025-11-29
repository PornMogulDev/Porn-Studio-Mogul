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
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Title", "Released", "Market", "Quality"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        layout.addWidget(self.table)

    def set_scenes(self, scenes: List[AISceneViewModel]):
        self.table.setRowCount(len(scenes))
        for row, scene in enumerate(scenes):
            self.table.setItem(row, 0, QTableWidgetItem(scene.title))
            self.table.setItem(row, 1, QTableWidgetItem(scene.date_str))
            self.table.setItem(row, 2, QTableWidgetItem(scene.market_group))
            
            quality_item = QTableWidgetItem(scene.quality_score_str)
            quality_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, quality_item)

    def clear(self):
        self.table.setRowCount(0)