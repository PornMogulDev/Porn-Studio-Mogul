from PyQt6.QtCore import Qt, QModelIndex, pyqtSignal, QPoint
from typing import List
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QMenu, QTableView, QHeaderView, QSplitter
)

from data.game_state import Talent
from ui.widgets.help_button import HelpButton
from ui.models.talent_table_model import TalentTableModel
from ui.widgets.view_menu_button import ViewMenuButton
from ui.widgets.role_details_widget import RoleDetailsWidget

class TalentTab(QWidget):
    # Signals for the Presenter
    standard_filters_changed = pyqtSignal(dict)
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
        
        # --- UI Components ---
        self.view_options_button: ViewMenuButton = None
        self.role_details_widget: RoleDetailsWidget = None
        self.talent_table_view: QTableView = None
        self.main_splitter: QSplitter = None
        
        self.setup_ui()

    def create_model_and_load(self, settings_manager, cup_size_order: List[str]):
        """Called by the presenter to inject dependencies and trigger initial load."""
        if self.talent_model is None:
            self.talent_model = TalentTableModel(
                settings_manager=settings_manager,
                cup_size_order=cup_size_order
            )
            self.talent_table_view.setModel(self.talent_model)
            self._configure_table_view_headers()
            self._load_and_apply_column_visibility()
            self._setup_visibility_controls()
            self.initial_load_requested.emit()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # --- Top controls container (outside the splitter) ---
        top_bar_layout = QHBoxLayout()
        help_btn = HelpButton("talent", self)
        self.view_options_button = ViewMenuButton(self)
        self.view_options_button.setToolTip("Show/Hide Panels & Columns")
        self.name_filter_input = QLineEdit(placeholderText="Filter by name...")
        self.advanced_filter_btn = QPushButton("Advanced Filter...")
        
        top_bar_layout.addWidget(help_btn)
        top_bar_layout.addWidget(self.view_options_button)
        top_bar_layout.addWidget(self.name_filter_input)
        top_bar_layout.addWidget(self.advanced_filter_btn)
        main_layout.addLayout(top_bar_layout)

        # --- Main Splitter Layout ---
        self.main_splitter = QSplitter(Qt.Orientation.Vertical, self)
        
        # Top Pane: Role Details
        self.role_details_widget = RoleDetailsWidget(self)
        self.role_details_widget.hide() # Start hidden
        
        # Bottom Pane: Talent Table
        self.talent_table_view = QTableView()
        self._configure_table_view_properties()

        self.main_splitter.addWidget(self.role_details_widget)
        self.main_splitter.addWidget(self.talent_table_view)
        main_layout.addWidget(self.main_splitter)

        # --- Fine-tune initial layout ---
        self.main_splitter.setSizes([200, 800]) # Give more space to table by default
        self.main_splitter.setStretchFactor(1, 1) # Allow table to grow more

        # --- Connections ---
        self.talent_table_view.customContextMenuRequested.connect(self.show_talent_list_context_menu)
        self.talent_table_view.doubleClicked.connect(self.show_talent_profile)
        self.name_filter_input.textChanged.connect(self.filter_talent_list)
        self.advanced_filter_btn.clicked.connect(lambda: self.open_advanced_filters_requested.emit(self.advanced_filters))
        self.view_options_button.visibility_changed.connect(self._on_visibility_changed)
        help_btn.help_requested.connect(self.help_requested)

    def _configure_table_view_properties(self):
        """Sets the static properties for the QTableView."""
        self.talent_table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.talent_table_view.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.talent_table_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.talent_table_view.verticalHeader().setVisible(False)
        self.talent_table_view.horizontalHeader().setStretchLastSection(True)
        self.talent_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.talent_table_view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.talent_table_view.setSortingEnabled(True)
        self.talent_table_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.talent_table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def _configure_table_view_headers(self):
        """Sets the initial column sizes."""
        header = self.talent_table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.talent_table_view.resizeColumnsToContents()
        header.resizeSection(0, 175) # Alias
        header.resizeSection(1, 50) # Age
        header.resizeSection(2, 100) # Gender
        header.resizeSection(3, 120) # Orientation
        header.resizeSection(4, 150) # Ethnicity
        header.resizeSection(5, 100) # Nationality
        header.resizeSection(6, 160) # Location
        header.resizeSection(7, 75) # Dick Size
        header.resizeSection(8, 75) # Cup Size
        header.resizeSection(9, 75) # Performance
        header.resizeSection(10, 75) # Acting
        header.resizeSection(11, 75) # Dom
        header.resizeSection(12, 75) # Sub
        header.resizeSection(13, 75) # Stamina
        header.resizeSection(14, 75) # Popularity
        header.resizeSection(15, 50) # Demand
        if self.talent_model and 'Demand' in self.talent_model.headers:
            demand_index = self.talent_model.headers.index('Demand')
            header.resizeSection(demand_index, 100)

    # --- Public Methods for Presenter ---

    def display_role_details(self, html: str):
        """Updates the content of the role details panel."""
        self.role_details_widget.update_role_details(html)
    
    def clear_role_details(self):
        """Clears the role details display and shows the placeholder."""
        self.role_details_widget.clear()

    def set_role_details_panel_visible(self, visible: bool):
        """Programmatically sets the visibility of the role details panel."""
        self.role_details_widget.setVisible(visible)
        self.view_options_button.update_item_visibility('__role_details', visible)
        if self.talent_model:
            self.talent_model.settings_manager.set_setting("talent_tab_role_details_visible", visible)

    def update_talent_list(self, talents: list):
        self.talent_model.update_data(talents)

    def on_filters_applied(self, filters: dict):
        self.advanced_filters = filters
        self.filter_talent_list()

    def refresh_from_state(self):
        self.filter_talent_list()
        
    def filter_talent_list(self):
        all_filters = self.advanced_filters.copy()
        all_filters['text'] = self.name_filter_input.text()
        self.standard_filters_changed.emit(all_filters)

    # --- Internal Logic & Slots ---

    def _setup_visibility_controls(self):
        """Configures the ViewMenuButton for columns and panels."""
        if not self.talent_model: return
        
        is_panel_visible = self.talent_model.settings_manager.get_setting("talent_tab_role_details_visible", False)
        self.role_details_widget.setVisible(is_panel_visible)
        
        items = [{
            'key': '__role_details',
            'name': 'Show Role Details',
            'visible': self.role_details_widget.isVisible(),
        }]
        
        column_items = [
            {
                'key': header, 'name': header,
                'visible': not self.talent_table_view.isColumnHidden(i),
            } for i, header in enumerate(self.talent_model.headers)
        ]
        items.extend(column_items)
        self.view_options_button.set_items(items)
    
    def _on_visibility_changed(self, key: str, visible: bool):
        """Handles visibility changes for columns and the role panel."""
        if not self.talent_model: return

        if key == '__role_details':
            self.set_role_details_panel_visible(visible)
        else:
            try:
                index = self.talent_model.headers.index(key)
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
        self.talent_model.settings_manager.set_setting("talent_tab_visible_columns", visible_columns)
        
    def _load_and_apply_column_visibility(self):
        if not self.talent_model: return
        visible_columns = self.talent_model.settings_manager.get_setting(
            "talent_tab_visible_columns", self.talent_model.headers
        )
        visible_set = set(visible_columns)
        for i, header_text in enumerate(self.talent_model.headers):
            self.talent_table_view.setColumnHidden(i, header_text not in visible_set)

    def show_talent_profile(self, index: QModelIndex):
        if talent := self.talent_model.data(index, Qt.ItemDataRole.UserRole):
            self.open_talent_profile_requested.emit(talent)

    def show_talent_list_context_menu(self, pos):
        index = self.talent_table_view.indexAt(pos)
        if not index.isValid(): return

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
                action.triggered.connect(lambda checked=False, t_ids=talent_ids, c_id=category['id']: 
                    self.add_talent_to_category_requested.emit(t_ids, c_id))
                add_menu.addAction(action)
        else:
            add_menu.setEnabled(False)

        remove_menu = menu.addMenu("Remove from Go-To Category...")
        if all_categories:
            for category in sorted(all_categories, key=lambda c: c['name']):
                action = QAction(category['name'], self)
                action.triggered.connect(lambda checked=False, t_ids=talent_ids, c_id=category['id']:  
                    self.remove_talent_from_category_requested.emit(t_ids, c_id))
                remove_menu.addAction(action)
        else:
            remove_menu.setEnabled(False)

        menu.exec(pos)