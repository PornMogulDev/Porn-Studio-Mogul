from PyQt6.QtCore import Qt, QAbstractListModel, QModelIndex, QPoint, QSize
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListView, QListWidget, QListWidgetItem,
    QAbstractItemView, QDialogButtonBox, QInputDialog, QMessageBox, QWidget, QMenu
)
from data.game_state import Talent
from ui.windows.talent_profile_window import TalentProfileWindow
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin

class GoToTalentListModel(QAbstractListModel):
    """A model for displaying a list of talents."""
    def __init__(self, talents: list[Talent] = None, parent=None):
        super().__init__(parent)
        self.talents = talents or []
        self.defaultSize = QSize(600, 500)

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
    ALL_TALENTS_ID = -1 # Sentinel value for the "All Talents" view

    def __init__(self, controller, ui_manager, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.ui_manager = ui_manager
        self.settings_manager = self.controller.settings_manager
        
        self.setWindowTitle("Go-To Talent Categories")
        self.setMinimumSize(600, 500)
        self.setup_ui()
        
        self.connect_signals()
        
        # Initial population
        self.refresh_categories()
        self._restore_geometry()

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
        # --- NEW: Enable context menu ---
        self.talent_list_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        right_layout.addWidget(self.talent_list_view)
        
        button_box = QDialogButtonBox()
        self.remove_btn = button_box.addButton("Remove From Category", QDialogButtonBox.ButtonRole.ActionRole)
        close_btn = button_box.addButton(QDialogButtonBox.StandardButton.Close)
        right_layout.addWidget(button_box)
        
        # Add panes to main layout
        main_layout.addWidget(left_pane, 2)
        main_layout.addWidget(right_pane, 3)
        
        close_btn.clicked.connect(self.accept)

    def connect_signals(self):
        self.category_list.currentItemChanged.connect(self.on_category_selected)
        
        self.new_category_btn.clicked.connect(self.create_new_category)
        self.rename_category_btn.clicked.connect(self.rename_selected_category)
        self.delete_category_btn.clicked.connect(self.delete_selected_category)
        
        self.remove_btn.clicked.connect(self.remove_selected_talents)
        self.talent_list_view.doubleClicked.connect(self.show_talent_profile)
        # --- NEW: Connect context menu signal ---
        self.talent_list_view.customContextMenuRequested.connect(self.show_talent_list_context_menu)

        self.controller.signals.go_to_categories_changed.connect(self.refresh_categories)
        self.controller.signals.go_to_list_changed.connect(self.refresh_current_talent_list)

    def refresh_categories(self):
        current_selection_id = None
        if current_item := self.category_list.currentItem():
            data = current_item.data(Qt.ItemDataRole.UserRole)
            current_selection_id = data if isinstance(data, int) else data.get('id')

        self.category_list.blockSignals(True)
        self.category_list.clear()

        all_item = QListWidgetItem("All Talents")
        all_item.setData(Qt.ItemDataRole.UserRole, self.ALL_TALENTS_ID)
        self.category_list.addItem(all_item)
        
        categories = self.controller.get_go_to_list_categories()
        for cat in categories:
            item = QListWidgetItem(cat['name'])
            item.setData(Qt.ItemDataRole.UserRole, cat)
            self.category_list.addItem(item)
            
        self.category_list.blockSignals(False)

        item_to_select = None
        if current_selection_id is not None:
            for i in range(self.category_list.count()):
                item = self.category_list.item(i)
                item_data = item.data(Qt.ItemDataRole.UserRole)
                item_id = item_data if isinstance(item_data, int) else item_data.get('id')
                if item_id == current_selection_id:
                    item_to_select = item
                    break
        
        if item_to_select:
            self.category_list.setCurrentItem(item_to_select)
        elif self.category_list.count() > 0:
            self.category_list.setCurrentRow(0)
        else:
            self.on_category_selected(None)

    def on_category_selected(self, current_item: QListWidgetItem):
        if not current_item:
            self.talent_model.update_data([])
            self.update_button_states()
            return

        category_data = current_item.data(Qt.ItemDataRole.UserRole)
        talents = []
        if category_data == self.ALL_TALENTS_ID:
            talents = self.controller.get_go_to_list_talents()
        elif isinstance(category_data, dict) and (category_id := category_data.get('id')):
            talents = self.controller.get_talents_in_go_to_category(category_id)
        
        sorted_talents = sorted(talents, key=lambda t: t.alias)
        self.talent_model.update_data(sorted_talents)
        self.update_button_states()
    
    def refresh_current_talent_list(self):
        """Refreshes the talent list for the currently selected category without changing selection."""
        self.on_category_selected(self.category_list.currentItem())

    def update_button_states(self):
        selected_item = self.category_list.currentItem()
        is_real_category, is_deletable = False, False
        
        if selected_item and isinstance(data := selected_item.data(Qt.ItemDataRole.UserRole), dict):
            is_real_category = True
            is_deletable = data.get('is_deletable', False)

        self.remove_btn.setEnabled(is_real_category)
        self.rename_category_btn.setEnabled(is_real_category)
        self.delete_category_btn.setEnabled(is_deletable)

    def create_new_category(self):
        name, ok = QInputDialog.getText(self, "New Category", "Enter category name:")
        if ok and name.strip():
            self.controller.create_go_to_list_category(name)

    def rename_selected_category(self):
        item = self.category_list.currentItem()
        if not item or not isinstance(data := item.data(Qt.ItemDataRole.UserRole), dict):
            return
        
        new_name, ok = QInputDialog.getText(self, "Rename Category", "Enter new name:", text=data.get('name'))
        if ok and new_name.strip() and new_name.strip() != data.get('name'):
            self.controller.rename_go_to_list_category(data.get('id'), new_name)

    def delete_selected_category(self):
        item = self.category_list.currentItem()
        if not item or not isinstance(data := item.data(Qt.ItemDataRole.UserRole), dict) or not data.get('is_deletable'):
            return

        reply = QMessageBox.question(self, "Confirm Delete",
                                     f"Are you sure you want to delete the category '{data.get('name')}'?\n"
                                     "All talent assignments to this category will be removed.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.controller.delete_go_to_list_category(data.get('id'))

    def show_talent_profile(self, index: QModelIndex):
        if not index.isValid(): return
        if talent := self.talent_model.data(index, Qt.ItemDataRole.UserRole):
            self.ui_manager.show_talent_profile(talent)

    # --- NEW METHOD ---
    def show_talent_list_context_menu(self, pos: QPoint):
        selected_indexes = self.talent_list_view.selectionModel().selectedIndexes()
        if not selected_indexes:
            return

        selected_talent_ids = [self.talent_model.data(index, Qt.ItemDataRole.UserRole).id 
                               for index in selected_indexes]
        
        menu = QMenu(self)
        all_categories = self.controller.get_go_to_list_categories()

        # --- "Add to..." Sub-menu ---
        add_menu = menu.addMenu("Add Selected to Category...")
        if all_categories:
            for category in sorted(all_categories, key=lambda c: c['name']):
                action = QAction(category['name'], self)
                action.triggered.connect(
                    lambda checked=False, t_ids=selected_talent_ids, c_id=category['id']: 
                    self.controller.add_talents_to_go_to_category(t_ids, c_id)
                )
                add_menu.addAction(action)
        else:
            add_menu.setEnabled(False)

        # --- "Remove from..." Sub-menu ---
        remove_menu = menu.addMenu("Remove Selected from Category...")
        if all_categories:
            for category in sorted(all_categories, key=lambda c: c['name']):
                action = QAction(category['name'], self)
                action.triggered.connect(
                    lambda checked=False, t_ids=selected_talent_ids, c_id=category['id']: 
                    self.controller.remove_talents_from_go_to_category(t_ids, c_id)
                )
                remove_menu.addAction(action)
        else:
            remove_menu.setEnabled(False)

        global_pos = self.talent_list_view.viewport().mapToGlobal(pos)
        menu.exec(global_pos)

    def remove_selected_talents(self):
        """Removes selected talents from the currently selected category."""
        category_item = self.category_list.currentItem()
        if not category_item or not isinstance(data := category_item.data(Qt.ItemDataRole.UserRole), dict):
            return
            
        selected_indexes = self.talent_list_view.selectionModel().selectedIndexes()
        if not selected_indexes: return
            
        ids_to_remove = [self.talent_model.data(index, Qt.ItemDataRole.UserRole).id 
                         for index in selected_indexes if self.talent_model.data(index, Qt.ItemDataRole.UserRole)]
        
        if ids_to_remove:
            self.controller.remove_talents_from_go_to_category(ids_to_remove, data.get('id'))