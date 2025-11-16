from PyQt6.QtCore import Qt, QModelIndex, pyqtSignal, QPoint
from typing import List
from PyQt6.QtCore import Qt,  QModelIndex, pyqtSignal, QPoint
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QMenu, QTableView, QHeaderView
 )

from data.game_state import Talent, Scene
from ui.widgets.help_button import HelpButton
from ui.models.talent_table_model import TalentTableModel
from ui.widgets.view_menu_button import ViewMenuButton

class TalentTab(QWidget):
    standard_filters_changed = pyqtSignal(dict)
    show_role_info_requested = pyqtSignal(int, int) # scene_id, vp_id
    clear_role_info_requested = pyqtSignal()
    scene_filter_selected = pyqtSignal(int)
    context_menu_requested = pyqtSignal(list, QPoint)
    add_talent_to_category_requested = pyqtSignal(list, int)
    remove_talent_from_category_requested = pyqtSignal(list, int)
    open_advanced_filters_requested = pyqtSignal(dict)
    open_talent_profile_requested = pyqtSignal(object)
    initial_load_requested = pyqtSignal()
    help_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.talent_model = None
        self.advanced_filters = {}
        self.view_options_button: ViewMenuButton = None
        self.setup_ui()

    def create_model_and_load(self, settings_manager, cup_size_order: List[str]):
        """Called by the presenter to inject dependencies and trigger initial load."""
        if self.talent_model is None:
            self.talent_model = TalentTableModel(
                settings_manager=settings_manager, 
                cup_size_order=cup_size_order,
                mode='casting' # MODIFIED: Use casting mode to show Demand column
             )
            self.talent_table_view.setModel(self.talent_model)
            self._configure_table_view_headers()
            # NEW: Load visibility settings and set up the control button
            self._load_and_apply_column_visibility()
            self._setup_column_visibility_control()
            self.initial_load_requested.emit()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Talent List Container (Bottom part) ---
        talent_list_container = QWidget()
        talent_list_layout = QVBoxLayout(talent_list_container)
        main_layout.addWidget(talent_list_container)

        top_bar_layout = QHBoxLayout()
        # Help 
        help_btn = HelpButton("talent"); top_bar_layout.addWidget(help_btn)
        # View Options
        self.view_options_button = ViewMenuButton(self)
        self.view_options_button.setToolTip("Show/Hide Columns")
        top_bar_layout.addWidget(self.view_options_button)
        # Name Filter
        self.name_filter_input = QLineEdit(placeholderText="Filter by name...")
        top_bar_layout.addWidget(self.name_filter_input)
        # Advanced Filter
        self.advanced_filter_btn = QPushButton("Advanced Filter...")
        top_bar_layout.addWidget(self.advanced_filter_btn)
        

        talent_list_layout.addLayout(top_bar_layout)
        
        self.talent_table_view = QTableView()
        self.talent_table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.talent_table_view.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.talent_table_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.talent_table_view.verticalHeader().setVisible(False)
        self.talent_table_view.horizontalHeader().setStretchLastSection(True)
        self.talent_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.talent_table_view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.talent_table_view.setSortingEnabled(True)
        self.talent_table_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)

        talent_list_layout.addWidget(self.talent_table_view)

        # --- Connections ---
        self.talent_table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.talent_table_view.customContextMenuRequested.connect(self.show_talent_list_context_menu)
        self.talent_table_view.doubleClicked.connect(self.show_talent_profile)
        
        self.name_filter_input.textChanged.connect(self.filter_talent_list)
        self.advanced_filter_btn.clicked.connect(lambda: self.open_advanced_filters_requested.emit(self.advanced_filters))
        self.view_options_button.visibility_changed.connect(self._on_column_visibility_changed) # NEW

        help_btn.help_requested.connect(self.help_requested)

    def _configure_table_view_headers(self):
        header = self.talent_table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.talent_table_view.resizeColumnsToContents()
        header.resizeSection(0, 150) # Alias
        header.resizeSection(1, 50) # Age
        header.resizeSection(2, 100) # Gender
        header.resizeSection(3, 120) # Orientation
        header.resizeSection(4, 150) # Ethnicity
        header.resizeSection(5, 120) # Nationality
        header.resizeSection(6, 150) # Location
        header.resizeSection(7, 75) # Dick Size
        header.resizeSection(8, 75) # Cup Size
        header.resizeSection(9, 100) # Performance
        header.resizeSection(10, 100) # Acting
        header.resizeSection(11, 100) # Dom
        header.resizeSection(12, 100) # Sub
        header.resizeSection(13, 100) # Stamina
        header.resizeSection(14, 100) # Popularity
        if self.talent_model and 'Demand' in self.talent_model.headers:
            header.resizeSection(15, 100) # Demand

    # --- Column Visibility ---

    def _setup_column_visibility_control(self):
        """Configures the ViewMenuButton to control column visibility."""
        if not self.talent_model: return
        items = [
            {
                'key': header,
                'name': header,
                'visible': not self.talent_table_view.isColumnHidden(i),
            } for i, header in enumerate(self.talent_model.headers)
        ]
        self.view_options_button.set_items(items)
    
    def _on_column_visibility_changed(self, column_key: str, visible: bool):
        """Hides or shows a column based on the key (header text)."""
        if not self.talent_model: return
        try:
            index = self.talent_model.headers.index(column_key)
            self.talent_table_view.setColumnHidden(index, not visible)
            self._save_column_visibility_settings()
        except ValueError:
            pass # Header not found
            
    def _save_column_visibility_settings(self):
        if not self.talent_model: return
            
        visible_columns = [
            self.talent_model.headers[i]
            for i in range(len(self.talent_model.headers))
            if not self.talent_table_view.isColumnHidden(i)
        ]
        
        self.talent_model.settings_manager.set_setting(
            "talent_tab_visible_columns", visible_columns # Use a unique key
        )
        
    def _load_and_apply_column_visibility(self):
        if not self.talent_model: return

        visible_columns = self.talent_model.settings_manager.get_setting(
            "talent_tab_visible_columns", self.talent_model.headers # Use a unique key
        )
        visible_set = set(visible_columns)
        
        for i, header_text in enumerate(self.talent_model.headers):
            self.talent_table_view.setColumnHidden(i, header_text not in visible_set)

    def update_talent_list(self, talents: list):
        self.talent_model.update_data(talents)

    def set_standard_filters_enabled(self, enabled: bool):
        self.advanced_filter_btn.setEnabled(enabled)
    
    def show_talent_profile(self, index: QModelIndex):
        if talent := self.talent_model.data(index, Qt.ItemDataRole.UserRole):
            self.open_talent_profile_requested.emit(talent)

    def on_filters_applied(self, filters: dict):
        self.advanced_filters = filters
        self.filter_talent_list()

    def show_talent_list_context_menu(self, pos):
        index = self.talent_table_view.indexAt(pos)
        if not index.isValid():
            return

        if not self.talent_table_view.selectionModel().isSelected(index):
            self.talent_table_view.clearSelection()
            self.talent_table_view.selectRow(index.row())

        selected_indexes = self.talent_table_view.selectionModel().selectedRows()
        selected_talents = [self.talent_model.data(idx, Qt.ItemDataRole.UserRole) for idx in selected_indexes]
        
        if selected_talents:
            global_pos = self.talent_table_view.viewport().mapToGlobal(pos)
            self.context_menu_requested.emit(selected_talents, global_pos)

    def display_talent_context_menu(self, talents: List[Talent], all_categories: list, pos: QPoint):
        menu = QMenu(self)
        talent_ids = [t.id for t in talents]

        add_menu = menu.addMenu("Add to Go-To Category...")
        if all_categories:
            for category in sorted(all_categories, key=lambda c: c['name']):
                action = QAction(category['name'], self)
                action.triggered.connect(
                    lambda checked=False, t_ids=talent_ids, c_id=category['id']: 
                    self.add_talent_to_category_requested.emit(t_ids, c_id)
                )
                add_menu.addAction(action)
        else:
            add_menu.setEnabled(False)

        remove_menu = menu.addMenu("Remove from Go-To Category...")
        if all_categories:
            for category in sorted(all_categories, key=lambda c: c['name']):
                action = QAction(category['name'], self)
                action.triggered.connect(
                    lambda checked=False, t_ids=talent_ids, c_id=category['id']:  
                    self.remove_talent_from_category_requested.emit(t_ids, c_id)
                )
                remove_menu.addAction(action)
        else:
            remove_menu.setEnabled(False)

        menu.exec(pos)

    def refresh_from_state(self):
        self.filter_talent_list()
        
    def filter_talent_list(self):
        all_filters = self.advanced_filters.copy()
        all_filters['text'] = self.name_filter_input.text()
        
        self.standard_filters_changed.emit(all_filters)