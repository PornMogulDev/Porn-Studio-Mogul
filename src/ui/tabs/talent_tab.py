from PyQt6.QtCore import Qt, QModelIndex, pyqtSignal, QPoint
from typing import Dict, List
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, pyqtSignal, QPoint
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QGroupBox, QComboBox, QCheckBox, QMenu,
    QGridLayout, QTableView, QTextEdit, QHeaderView
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

        # --- Top Container for Filters and Role Info ---
        top_container = QWidget()
        main_layout.addWidget(top_container, 3)
        top_container_layout = QHBoxLayout(top_container)

        # --- Role Filter Group (Left side of top container) ---
        role_filter_group = QGroupBox("Role Info"); role_filter_layout = QGridLayout(role_filter_group)
        role_filter_layout.addWidget(QLabel("Scene:"), 0, 0); role_filter_layout.addWidget(QLabel("Role:"), 1, 0)
        self.scene_filter_combo = QComboBox(); self.role_filter_combo = QComboBox()
        role_filter_layout.addWidget(self.scene_filter_combo, 0, 1); role_filter_layout.addWidget(self.role_filter_combo, 1, 1)

        self.show_role_info_btn = QPushButton("Show Role Info"); self.clear_role_filter_btn = QPushButton("Clear")
        role_filter_layout.addWidget(self.show_role_info_btn, 2, 1); role_filter_layout.addWidget(self.clear_role_filter_btn, 2, 0)
        self.filter_by_reqs_checkbox = QCheckBox("Filter by requirements"); self.filter_by_reqs_checkbox.setEnabled(False)
        self.hide_refusals_checkbox = QCheckBox("Hide refusals"); self.hide_refusals_checkbox.setEnabled(False)
        role_filter_layout.addWidget(self.filter_by_reqs_checkbox, 3, 0, 1, 2)
        role_filter_layout.addWidget(self.hide_refusals_checkbox, 4, 0, 1, 2)
        top_container_layout.addWidget(role_filter_group)

        # --- Role Info Group (Right side of top container) ---
        self.role_info_group = QGroupBox("Role Details")
        role_info_layout = QVBoxLayout(self.role_info_group)
        self.role_info_display = QTextEdit()
        self.role_info_display.setReadOnly(True)
        role_info_layout.addWidget(self.role_info_display)
        top_container_layout.addWidget(self.role_info_group)

        # --- Talent List Container (Bottom part) ---
        talent_list_container = QWidget()
        talent_list_layout = QVBoxLayout(talent_list_container)
        main_layout.addWidget(talent_list_container, 7)

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
        
        self.scene_filter_combo.currentIndexChanged.connect(self.on_scene_filter_selected)
        self.show_role_info_btn.clicked.connect(self.on_show_role_info)
        self.clear_role_filter_btn.clicked.connect(self.on_clear_role_filter)
        self.filter_by_reqs_checkbox.toggled.connect(self.filter_talent_list)
        self.hide_refusals_checkbox.toggled.connect(self.filter_talent_list)

        help_btn.help_requested.connect(self.help_requested)

    def _configure_table_view_headers(self):
        self.talent_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.talent_table_view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch) # Alias

    def update_talent_list(self, talents: list):
        self.talent_model.update_data(talents)

    def update_scene_dropdown(self, scenes: list):
        self.scene_filter_combo.blockSignals(True)
        current_id = self.scene_filter_combo.currentData()
        self.scene_filter_combo.clear(); self.scene_filter_combo.addItem("-- Select a Scene --", -1)
        for scene in scenes: self.scene_filter_combo.addItem(scene['title'], scene['id'])
        
        idx = self.scene_filter_combo.findData(current_id)
        if idx != -1: self.scene_filter_combo.setCurrentIndex(idx)
        else: self.update_role_dropdown([])
        
        self.scene_filter_combo.blockSignals(False)

    def display_role_info(self, html: str):
        self.role_info_display.setHtml(html)
        self.role_info_group.setVisible(True)

    def clear_role_info(self):
        self.role_info_display.clear()
        self.role_info_group.setVisible(False)
        self.filter_by_reqs_checkbox.setEnabled(False); self.filter_by_reqs_checkbox.setChecked(False)
        self.hide_refusals_checkbox.setEnabled(False); self.hide_refusals_checkbox.setChecked(False)

    def update_role_dropdown(self, roles: list):
        self.role_filter_combo.blockSignals(True)
        self.role_filter_combo.clear(); self.role_filter_combo.addItem("-- Select a Role --", -1)
        for role in roles: self.role_filter_combo.addItem(role['name'], role['id'])
        self.role_filter_combo.blockSignals(False)
        self.set_role_filter_enabled(len(roles) > 0)

    def set_standard_filters_enabled(self, enabled: bool):
        self.advanced_filter_btn.setEnabled(enabled)

    def set_role_filter_enabled(self, enabled: bool):
        self.show_role_info_btn.setEnabled(enabled)
        self.role_filter_combo.setEnabled(enabled)
    
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

        if self.role_info_group.isVisible():
            all_filters['role_filter'] = {
                'active': True,
                'scene_id': self.scene_filter_combo.currentData(),
                'vp_id': self.role_filter_combo.currentData(),
                'filter_by_reqs': self.filter_by_reqs_checkbox.isChecked(),
                'hide_refusals': self.hide_refusals_checkbox.isChecked()
            }
        else:
             all_filters['role_filter'] = {'active': False}

        self.standard_filters_changed.emit(all_filters)
        
    def on_scene_filter_selected(self, index: int):
        scene_id = self.scene_filter_combo.itemData(index) or -1
        self.scene_filter_selected.emit(scene_id)

    def on_show_role_info(self):
        scene_id = self.scene_filter_combo.currentData()
        vp_id = self.role_filter_combo.currentData()
        if scene_id > 0 and vp_id > 0:
            self.show_role_info_requested.emit(scene_id, vp_id)

    def on_clear_role_filter(self):
        if self.scene_filter_combo.currentIndex() != 0:
            self.scene_filter_combo.setCurrentIndex(0)
        else:
            # If it was already at index 0, the signal won't fire, so we manually clear.
            self.update_role_dropdown([])
        self.clear_role_info_requested.emit()