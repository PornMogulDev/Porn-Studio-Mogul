from PyQt6.QtCore import Qt, QAbstractListModel, QModelIndex
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QListView,
    QAbstractItemView, QDialogButtonBox
)
from game_state import Talent
from ui.dialogs.talent_profile_dialog import TalentProfileDialog
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin

class GoToTalentListModel(QAbstractListModel):
    """A model for displaying a list of talents."""
    def __init__(self, talents: list[Talent] = None, parent=None):
        super().__init__(parent)
        self.talents = talents or []

    def data(self, index: QModelIndex, role: int):
        if not index.isValid():
            return None
        talent = self.talents[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            display_text = talent.alias
            if talent.fatigue > 0:
                display_text += f" (Fatigued)"
            return display_text
        
        if role == Qt.ItemDataRole.UserRole:
            return talent
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()):
        return len(self.talents)

    def update_data(self, new_talents: list[Talent]):
        """Resets the model with a new list of talents."""
        self.beginResetModel()
        self.talents = new_talents
        self.endResetModel()

class GoToTalentDialog(GeometryManagerMixin, QDialog):
    """A dialog to view and manage the Go-To talent list."""
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.settings_manager = self.controller.settings_manager
        
        self.setWindowTitle("Go-To Talent List")
        self.setMinimumSize(400, 500)
        self.setup_ui()
        
        # Connect signals
        self.remove_btn.clicked.connect(self.remove_selected_talents)
        self.controller.signals.go_to_list_changed.connect(self.refresh_list)
        
        # Initial population
        self.refresh_list()
        self._restore_geometry()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        # List View
        self.list_view = QListView()
        self.model = GoToTalentListModel()
        self.list_view.setModel(self.model)
        self.list_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        main_layout.addWidget(self.list_view)
        
        # Button Box
        button_box = QDialogButtonBox()
        self.remove_btn = button_box.addButton("Remove Selected", QDialogButtonBox.ButtonRole.ActionRole)
        close_btn = button_box.addButton(QDialogButtonBox.StandardButton.Close)
        main_layout.addWidget(button_box)
        
        close_btn.clicked.connect(self.accept)

        self.list_view.doubleClicked.connect(self.show_talent_profile)

    def show_talent_profile(self, index: QModelIndex):
        if not index.isValid():
            return
        talent = self.model.data(index, Qt.ItemDataRole.UserRole)
        if talent:
            dialog = TalentProfileDialog(talent, self.controller, self)
            dialog.exec()

    def refresh_list(self):
        """Fetches the latest go-to list from the controller and updates the model."""
        # Use the new controller method that queries the database directly.
        go_to_talents = self.controller.get_go_to_list_talents()
        # Sort by alias for consistent display
        sorted_talents = sorted(go_to_talents, key=lambda t: t.alias)
        self.model.update_data(sorted_talents)

    def remove_selected_talents(self):
        """Removes the selected talents from the go-to list via the controller."""
        selected_indexes = self.list_view.selectionModel().selectedIndexes()
        if not selected_indexes:
            return
            
        ids_to_remove = []
        for index in selected_indexes:
            talent = self.model.data(index, Qt.ItemDataRole.UserRole)
            if talent:
                ids_to_remove.append(talent.id)
        
        if ids_to_remove:
            self.controller.remove_talents_from_go_to_list(ids_to_remove)