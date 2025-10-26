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

class HireWindow(QWidget):
    standard_filters_changed = pyqtSignal(dict)
    show_role_info_requested = pyqtSignal(int, int) # scene_id, vp_id
    clear_role_info_requested = pyqtSignal()
    scene_filter_selected = pyqtSignal(int)
    context_menu_requested = pyqtSignal(object, QPoint)
    add_talent_to_category_requested = pyqtSignal(int, int)
    remove_talent_from_category_requested = pyqtSignal(int, int)
    open_advanced_filters_requested = pyqtSignal(dict)
    open_talent_profile_requested = pyqtSignal(object)
    initial_load_requested = pyqtSignal()
    help_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.talent_model = None
        self.advanced_filters = {}
        self.setup_ui()

    def create_model_and_load(self, settings_manager, boob_cup_order: List[str]):
        """Called by the presenter to inject dependencies and trigger initial load."""
        if self.talent_model is None:
            self.talent_model = TalentTableModel(
                settings_manager=settings_manager, 
                boob_cup_order=boob_cup_order,
                mode='default' # Explicitly use default mode
             )
            self.talent_table_view.setModel(self.talent_model)
            self._configure_table_view_headers()
            self.initial_load_requested.emit()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Talent List Container (Bottom part) ---
        talent_list_container = QWidget()
        talent_list_layout = QVBoxLayout(talent_list_container)
        main_layout.addWidget(talent_list_container)

        top_bar_layout = QHBoxLayout()
        help_btn = HelpButton("talent"); top_bar_layout.addWidget(help_btn)
        self.name_filter_input = QLineEdit(placeholderText="Filter by name...")
        top_bar_layout.addWidget(self.name_filter_input)
        self.advanced_filter_btn = QPushButton("Advanced Filter...")

        top_bar_layout.addWidget(self.advanced_filter_btn)
        talent_list_layout.addLayout(top_bar_layout)
        
        self.talent_table_view = QTableView()
        self.talent_table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
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

        help_btn.help_requested.connect(self.help_requested)

    def _configure_table_view_headers(self):
        self.talent_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.talent_table_view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch) # Alias

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
        if not index.isValid(): return
        if talent := self.talent_model.data(index, Qt.ItemDataRole.UserRole):
            global_pos = self.talent_table_view.viewport().mapToGlobal(pos)
            self.context_menu_requested.emit(talent, global_pos)

    def display_talent_context_menu(self, talent: Talent, all_categories: list, talent_categories: list, pos: QPoint):
        menu = QMenu(self)

        add_menu = menu.addMenu("Add to Go-To Category...")
        if all_categories:
            for category in sorted(all_categories, key=lambda c: c['name']):
                action = QAction(category['name'], self)
                action.triggered.connect(
                    lambda checked=False, t_id=talent.id, c_id=category['id']: 
                    self.add_talent_to_category_requested.emit(t_id, c_id)
                )
                add_menu.addAction(action)
        else:
            add_menu.setEnabled(False)

        remove_menu = menu.addMenu("Remove from Go-To Category...")
        if talent_categories:
            for category in sorted(talent_categories, key=lambda c: c['name']):
                action = QAction(category['name'], self)
                action.triggered.connect(
                    lambda checked=False, t_id=talent.id, c_id=category['id']: 
                    self.remove_talent_from_category_requested.emit(t_id, c_id)
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