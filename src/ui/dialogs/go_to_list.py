from PyQt6.QtCore import Qt, QAbstractListModel, QModelIndex, QPoint, QSize
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListView, QListWidget, QListWidgetItem,
    QAbstractItemView, QDialogButtonBox, QInputDialog, QMessageBox, QWidget, QMenu
)
from data.game_state import Talent
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin
### MODIFIED: Import the presenter and the shared sentinel value
from ui.presenters.go_to_list_presenter import GoToListPresenter, ALL_TALENTS_ID

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
    """A dialog to view and manage Go-To talent list categories."""
    # ### MODIFIED: The sentinel value is now imported from the presenter.
    # ALL_TALENTS_ID is now imported.

    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.presenter: GoToListPresenter | None = None # Initialize to None
        self.settings_manager = settings_manager # Mixin needs this
        
        self.setWindowTitle("Go-To Talent Categories")
        self.setMinimumSize(600, 500)
        self.defaultSize = QSize(600, 500)
        
        self.setup_ui()
        self.connect_signals()
        
        # Geometry is restored here, before the presenter initializes,
        # which is perfectly fine.
        self._restore_geometry()

    # --- NEW METHOD ---
    def set_presenter(self, presenter: GoToListPresenter):
        """Sets the presenter for the dialog and triggers initial data load."""
        self.presenter = presenter
        self.presenter.initialize()

    def setup_ui(self):
        main_layout = QHBoxLayout(self)

        # --- Left Pane (Categories) ---
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.category_list = QListWidget()
        left_layout.addWidget(self.category_list)
        
        category_button_layout = QHBoxLayout()
        self.new_category_btn = QPushButton("New")
        self.rename_category_btn = QPushButton("Rename")
        self.delete_category_btn = QPushButton("Delete")
        category_button_layout.addWidget(self.new_category_btn)
        category_button_layout.addWidget(self.rename_category_btn)
        category_button_layout.addWidget(self.delete_category_btn)
        left_layout.addLayout(category_button_layout)
        
        # --- Right Pane (Talents) ---
        right_pane = QWidget()
        right_layout = QVBoxLayout(right_pane)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        self.talent_list_view = QListView()
        self.talent_model = GoToTalentListModel()
        self.talent_list_view.setModel(self.talent_model)
        self.talent_list_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.talent_list_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        right_layout.addWidget(self.talent_list_view)
        
        button_box = QDialogButtonBox()
        self.remove_btn = button_box.addButton("Remove From Category", QDialogButtonBox.ButtonRole.ActionRole)
        close_btn = button_box.addButton(QDialogButtonBox.StandardButton.Close)
        right_layout.addWidget(button_box)
        
        main_layout.addWidget(left_pane, 2)
        main_layout.addWidget(right_pane, 3)
        
        close_btn.clicked.connect(self.accept)

    def connect_signals(self):
        # ### MODIFIED: Only connect UI widget signals. Controller signals are handled by the presenter.
        self.category_list.currentItemChanged.connect(self.on_category_selected)
        
        self.new_category_btn.clicked.connect(self.create_new_category)
        self.rename_category_btn.clicked.connect(self.rename_selected_category)
        self.delete_category_btn.clicked.connect(self.delete_selected_category)
        
        self.remove_btn.clicked.connect(self.remove_selected_talents)
        self.talent_list_view.doubleClicked.connect(self.show_talent_profile)
        self.talent_list_view.customContextMenuRequested.connect(self.show_talent_list_context_menu)

    ### NEW: Method for the presenter to update the category list.
    def display_categories(self, categories: list[dict], selected_id: int):
        self.category_list.blockSignals(True)
        self.category_list.clear()

        all_item = QListWidgetItem("All Talents")
        all_item.setData(Qt.ItemDataRole.UserRole, ALL_TALENTS_ID)
        self.category_list.addItem(all_item)
        
        for cat in categories:
            item = QListWidgetItem(cat['name'])
            item.setData(Qt.ItemDataRole.UserRole, cat['id'])
            self.category_list.addItem(item)
            
        self.category_list.blockSignals(False)

        item_to_select = None
        for i in range(self.category_list.count()):
            item = self.category_list.item(i)
            item_id = item.data(Qt.ItemDataRole.UserRole)
            if item_id == selected_id:
                item_to_select = item
                break
        
        if item_to_select:
            self.category_list.setCurrentItem(item_to_select)
        elif self.category_list.count() > 0:
            self.category_list.setCurrentRow(0)
        else:
            # Explicitly trigger selection logic for the null state
            self.on_category_selected(None)

    ### NEW: Method for the presenter to update the talent list.
    def display_talents(self, talents: list[Talent]):
        self.talent_model.update_data(talents)

    def on_category_selected(self, current_item: QListWidgetItem | None):
        ### MODIFIED: This method now only reports the selection to the presenter.
        if not current_item:
            self.presenter.select_category(None)
            return

        category_id = current_item.data(Qt.ItemDataRole.UserRole)
        self.presenter.select_category(category_id)
    
    ### MODIFIED: Button state logic is gone. This method just applies the state given by the presenter.
    def update_button_states(self, states: dict):
        self.remove_btn.setEnabled(states.get('remove_enabled', False))
        self.rename_category_btn.setEnabled(states.get('rename_enabled', False))
        self.delete_category_btn.setEnabled(states.get('delete_enabled', False))

    def create_new_category(self):
        ### MODIFIED: Delegates the action to the presenter after getting user input.
        name, ok = QInputDialog.getText(self, "New Category", "Enter category name:")
        if ok and name.strip():
            self.presenter.create_category(name.strip())

    def rename_selected_category(self):
        ### MODIFIED: Gets current data from the presenter and delegates the action.
        current_cat_info = self.presenter.get_current_category_info()
        if not current_cat_info:
            return
        
        new_name, ok = QInputDialog.getText(self, "Rename Category", "Enter new name:", text=current_cat_info.get('name'))
        if ok and new_name.strip() and new_name.strip() != current_cat_info.get('name'):
            self.presenter.rename_current_category(new_name.strip())

    def delete_selected_category(self):
        ### MODIFIED: Gets current data from the presenter and delegates the action.
        current_cat_info = self.presenter.get_current_category_info()
        if not current_cat_info or not current_cat_info.get('is_deletable'):
            return

        reply = QMessageBox.question(self, "Confirm Delete",
                                     f"Are you sure you want to delete the category '{current_cat_info.get('name')}'?\n"
                                     "All talent assignments to this category will be removed.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.presenter.delete_current_category()

    def show_talent_profile(self, index: QModelIndex):
        ### MODIFIED: Delegates the action to the presenter.
        if not index.isValid(): return
        if talent := self.talent_model.data(index, Qt.ItemDataRole.UserRole):
            self.presenter.show_talent_profile(talent)

    def show_talent_list_context_menu(self, pos: QPoint):
        ### MODIFIED: Builds the menu from a simple model provided by the presenter.
        selected_indexes = self.talent_list_view.selectionModel().selectedIndexes()
        if not selected_indexes:
            return

        selected_talent_ids = [self.talent_model.data(index, Qt.ItemDataRole.UserRole).id 
                               for index in selected_indexes]
        
        # Get the menu structure from the presenter
        menu_model = self.presenter.get_context_menu_model()
        menu = QMenu(self)

        # --- "Add to..." Sub-menu ---
        add_menu = menu.addMenu("Add Selected to Category...")
        if add_model := menu_model.get('add_to'):
            for category_data in add_model:
                action = QAction(category_data['name'], self)
                action.triggered.connect(
                    lambda checked=False, t_ids=selected_talent_ids, c_id=category_data['id']: 
                    self.presenter.add_talents_to_category(t_ids, c_id)
                )
                add_menu.addAction(action)
        else:
            add_menu.setEnabled(False)

        # --- "Remove from..." Sub-menu ---
        remove_menu = menu.addMenu("Remove Selected from Category...")
        if remove_model := menu_model.get('remove_from'):
            for category_data in remove_model:
                action = QAction(category_data['name'], self)
                action.triggered.connect(
                    lambda checked=False, t_ids=selected_talent_ids, c_id=category_data['id']: 
                    self.presenter.remove_talents_from_category(t_ids, c_id)
                )
                remove_menu.addAction(action)
        else:
            remove_menu.setEnabled(False)

        global_pos = self.talent_list_view.viewport().mapToGlobal(pos)
        menu.exec(global_pos)

    def remove_selected_talents(self):
        ### MODIFIED: Delegates the action to the presenter.
        selected_indexes = self.talent_list_view.selectionModel().selectedIndexes()
        if not selected_indexes: return
            
        ids_to_remove = [self.talent_model.data(index, Qt.ItemDataRole.UserRole).id 
                         for index in selected_indexes if self.talent_model.data(index, Qt.ItemDataRole.UserRole)]
        
        if ids_to_remove:
            self.presenter.remove_talents_from_current_category(ids_to_remove)

    def closeEvent(self, event):
            """Ensures presenter disconnects from global signals when the dialog is closed."""
            if self.presenter:
                self.presenter.disconnect_signals()
            super().closeEvent(event)