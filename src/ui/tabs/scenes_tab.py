from typing import List, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QAbstractItemView, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal, QModelIndex

from data.game_state import Scene
from ui.models.scene_model import SceneTableModel, SceneSortFilterProxyModel
from ui.view_models import SceneViewModel

class ScenesTab(QWidget):
    """
    A "dumb" view for displaying shot and released scenes. It renders data
    provided by the ScenesTabPresenter and emits signals for user actions.
    """
    # Signals emitted to the presenter
    selection_changed = pyqtSignal(object)       # Emits selected Scene object or None
    manage_button_clicked = pyqtSignal(object)   # Emits selected Scene object
    item_double_clicked = pyqtSignal(int)        # Emits scene_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.source_model = SceneTableModel()
        self.proxy_model = SceneSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.source_model)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.scene_table = QTableView()
        self.scene_table.setModel(self.proxy_model)
        self.scene_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.scene_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.scene_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.scene_table.setSortingEnabled(True)
        self.scene_table.horizontalHeader().setStretchLastSection(True)
        self.scene_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.scene_table.sortByColumn(2, Qt.SortOrder.AscendingOrder)
        layout.addWidget(self.scene_table)

        button_layout = QHBoxLayout()
        self.manage_scene_btn = QPushButton("Release Selected Scene")
        button_layout.addWidget(self.manage_scene_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        # --- Signal Connections (View -> Presenter) ---
        self.scene_table.doubleClicked.connect(self._on_item_double_clicked)
        self.manage_scene_btn.clicked.connect(self._on_manage_button_clicked)
        self.scene_table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        
        # Initial state
        self.manage_scene_btn.setEnabled(False)

    def update_scene_list(self, scene_vms: List[SceneViewModel], raw_scenes: List[Scene]):
        """Receives new data from the presenter and updates the table model."""
        self.source_model.update_data(scene_vms, raw_scenes)

    def update_button_state(self, text: str, is_enabled: bool):
        """A simple "setter" method for the presenter to control the main action button."""
        self.manage_scene_btn.setText(text)
        self.manage_scene_btn.setEnabled(is_enabled)
        
    def _get_selected_scene(self) -> Optional[Scene]:
        """Helper method to get the currently selected raw Scene object from the model."""
        selected_indexes = self.scene_table.selectionModel().selectedRows()
        if not selected_indexes:
            return None
            
        proxy_index = selected_indexes[0]
        source_index = self.proxy_model.mapToSource(proxy_index)
        return self.source_model.data(source_index, Qt.ItemDataRole.UserRole)

    def _on_selection_changed(self):
        """Internal slot that fires when selection changes and notifies the presenter."""
        selected_scene = self._get_selected_scene()
        self.selection_changed.emit(selected_scene)

    def _on_manage_button_clicked(self):
        """Internal slot that notifies the presenter when the action button is clicked."""
        selected_scene = self._get_selected_scene()
        if selected_scene:
            self.manage_button_clicked.emit(selected_scene)

    def _on_item_double_clicked(self, proxy_index: QModelIndex):
        """Internal slot that notifies the presenter of a double-click event."""
        source_index = self.proxy_model.mapToSource(proxy_index)
        scene = self.source_model.data(source_index, Qt.ItemDataRole.UserRole)
        if scene:
            self.item_double_clicked.emit(scene.id)