from typing import List
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QTableView, QHeaderView, QLabel
from PyQt6.QtCore import pyqtSignal, Qt, QModelIndex

from data.game_state import Talent
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin
from ui.tabs.talent_tab import TalentTableModel

class RoleCastingDialog(GeometryManagerMixin, QDialog):
    hire_requested = pyqtSignal(object) # talent
    name_filter_changed = pyqtSignal(str)

    def __init__(self, controller, scene_id: int, vp_id: int, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.scene_id = scene_id
        self.vp_id = vp_id

        self.talent_model = TalentTableModel(settings_manager=self.controller.settings_manager)

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Hire Talent for Role")
        self.setMinimumSize(800, 600)
        
        self.setup_ui()
        self._connect_signals()
        self._restore_geometry()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        top_bar_layout = QHBoxLayout()
        top_bar_layout.addWidget(QLabel("Filter by name:"))
        self.name_filter_input = QLineEdit()
        top_bar_layout.addWidget(self.name_filter_input)
        main_layout.addLayout(top_bar_layout)

        self.talent_table_view = QTableView()
        self.talent_table_view.setModel(self.talent_model)
        self.talent_table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.talent_table_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.talent_table_view.verticalHeader().setVisible(False)
        self.talent_table_view.setSortingEnabled(True)
        self.talent_table_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self._configure_table_view_headers()
        main_layout.addWidget(self.talent_table_view)

    def _connect_signals(self):
        self.name_filter_input.textChanged.connect(self.name_filter_changed)
        self.talent_table_view.doubleClicked.connect(self._on_talent_selected)

    def _configure_table_view_headers(self):
        header = self.talent_table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch) # Alias

    def update_talent_table(self, talents: List[Talent]):
        self.talent_model.update_data(talents)

    def _on_talent_selected(self, index: QModelIndex):
        if talent := self.talent_model.data(index, Qt.ItemDataRole.UserRole):
            self.hire_requested.emit(talent)