from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QAbstractItemView, QHeaderView
)
from PyQt6.QtCore import Qt
from ui.models.scene_model import SceneTableModel, SceneSortFilterProxyModel
from ui.dialogs.shot_scene_details_dialog import ShotSceneDetailsDialog

class ScenesTab(QWidget):
    def __init__(self, controller, uimanager):
        super().__init__()
        self.controller = controller
        self.uimanager = uimanager
        self.source_model = SceneTableModel(controller=self.controller)
        self.proxy_model = SceneSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.source_model)
        self.setup_ui()
        
        self.controller.signals.scenes_changed.connect(self.refresh_view)
        self.scene_table.doubleClicked.connect(self.view_scene_details)
        self.manage_scene_btn.clicked.connect(self.manage_scene)
        self.scene_table.selectionModel().selectionChanged.connect(self.update_button_states)
        self.refresh_view()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.scene_table = QTableView()
        self.scene_table.setModel(self.proxy_model)
        self.scene_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
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

    def refresh_view(self):
        shot_scenes = self.controller.get_shot_scenes()
        self.source_model.setScenes(shot_scenes)
        self.update_button_states()

    def _get_selected_scene(self):
        selected_indexes = self.scene_table.selectionModel().selectedRows()
        if len(selected_indexes) != 1: return None
        source_index = self.proxy_model.mapToSource(selected_indexes[0])
        return self.source_model.data(source_index, Qt.ItemDataRole.UserRole)

    def update_button_states(self):
        selected_scene = self._get_selected_scene()
        if not selected_scene:
            self.manage_scene_btn.setEnabled(False)
            self.manage_scene_btn.setText("Release Selected Scene")
            return

        if selected_scene.status == 'ready_to_release':
            self.manage_scene_btn.setEnabled(True)
            self.manage_scene_btn.setText("Release Scene")
        elif selected_scene.status == 'shot':
            self.manage_scene_btn.setEnabled(True)
            self.manage_scene_btn.setText("Manage Post-Production")
        else:
            self.manage_scene_btn.setEnabled(False)
            self.manage_scene_btn.setText("Release Selected Scene")

    def manage_scene(self): 
        selected_scene = self._get_selected_scene()
        if not selected_scene: return
        
        if selected_scene.status == 'ready_to_release':
            self.controller.release_scene(selected_scene.id)
        elif selected_scene.status == 'shot':
            # This is handled by the double-click/details dialog
            self.uimanager.show_shot_scene_details(selected_scene.id)
            
    def view_scene_details(self, proxy_index):
        source_index = self.proxy_model.mapToSource(proxy_index)
        scene = self.source_model.data(source_index, Qt.ItemDataRole.UserRole)
        if scene:
            self.uimanager.show_shot_scene_details(scene.id)