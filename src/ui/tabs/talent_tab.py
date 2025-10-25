from PyQt6.QtCore import Qt, QModelIndex, pyqtSignal, QPoint
from typing import Dict, List
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, pyqtSignal, QPoint
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QGroupBox, QComboBox, QStackedWidget, QMenu,
    QMessageBox, QScrollArea, QListWidget, QListWidgetItem,
    QGridLayout, QTableView, QTextEdit, QHeaderView
 )
from collections import defaultdict

from data.game_state import Talent, Scene
from ui.widgets.help_button import HelpButton
from ui.dialogs.scene_dialog import SceneDialog
from utils.formatters import format_orientation, format_physical_attribute

class TalentTableModel(QAbstractTableModel):
    def __init__(self, talents: List[Talent] = None, parent=None):
        super().__init__(parent)
        self.talents = talents or []
        self.headers = ["Alias", "Age", "Gender", "Perf.", "Act.", "Stam.", "Pop."]
    def data(self, index: QModelIndex, role: int):
        if not index.isValid(): return None
        talent = self.talents[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0: return talent.alias
            if col == 1: return talent.age
            if col == 2: return talent.gender
            if col == 3: return f"{talent.performance:.2f}"
            if col == 4: return f"{talent.acting:.2f}"
            if col == 5: return f"{talent.stamina:.2f}"
            if col == 6: return f"{sum(talent.popularity.values()):.2f}"
        elif role == Qt.ItemDataRole.UserRole:
            return talent
        return None
    def rowCount(self, parent: QModelIndex = QModelIndex()): return len(self.talents)
    def columnCount(self, parent: QModelIndex = QModelIndex()): return len(self.headers)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return None

    def update_data(self, new_talents: List[Talent]):
        self.beginResetModel()
        self.talents = new_talents
        self.endResetModel()

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
        self.talent_model = TalentTableModel()
        self.advanced_filters = {}
        self.setup_ui()
        self.initial_load_requested.emit()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        top_container = QWidget()
        top_layout = QHBoxLayout(top_container)

        filter_container = QWidget()
        filter_layout = QVBoxLayout(filter_container)

        help_btn = HelpButton("talent")
        filter_layout.addWidget(help_btn)

        role_filter_group = QGroupBox("Filter for Role"); role_filter_layout = QGridLayout(role_filter_group)
        role_filter_layout.addWidget(QLabel("Scene:"), 0, 0); role_filter_layout.addWidget(QLabel("Role:"), 1, 0)
        self.scene_filter_combo = QComboBox(); self.role_filter_combo = QComboBox()
        role_filter_layout.addWidget(self.scene_filter_combo, 0, 1); role_filter_layout.addWidget(self.role_filter_combo, 1, 1)
        self.apply_role_filter_btn = QPushButton("Show Role Info"); self.clear_role_filter_btn = QPushButton("Clear")
        role_filter_layout.addWidget(self.apply_role_filter_btn, 2, 1); role_filter_layout.addWidget(self.clear_role_filter_btn, 2, 0)
        filter_layout.addWidget(role_filter_group)

        self.role_info_group = QGroupBox("Role Details")
        self.role_info_group.setVisible(False)
        role_info_layout = QVBoxLayout(self.role_info_group)
        self.role_info_display = QTextEdit()
        self.role_info_display.setReadOnly(True)
        role_info_layout.addWidget(self.role_info_display)
        filter_layout.addWidget(self.role_info_group)
        filter_layout.addStretch()
        top_layout.addWidget(filter_container, 3)

        talent_list_container = QWidget()
        talent_list_layout = QVBoxLayout(talent_list_container)

        self.name_filter_input = QLineEdit(placeholderText="Filter by name...")
        self.advanced_filter_btn = QPushButton("Advanced Filter...")
        talent_list_layout.addWidget(self.name_filter_input)
        talent_list_layout.addWidget(self.advanced_filter_btn)
        
        self.talent_table_view = QTableView()
        self.talent_table_view.setModel(self.talent_model)
        self.talent_table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.talent_table_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.talent_table_view.verticalHeader().setVisible(False)
        self.talent_table_view.horizontalHeader().setStretchLastSection(True)
        self.talent_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.talent_table_view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        
        talent_list_layout.addWidget(self.talent_table_view)
        top_layout.addWidget(talent_list_container, 7)
        main_layout.addWidget(top_container)

        self.talent_table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.talent_table_view.customContextMenuRequested.connect(self.show_talent_list_context_menu)
        self.talent_table_view.doubleClicked.connect(self.show_talent_profile)
        
        self.name_filter_input.textChanged.connect(self.filter_talent_list)
        self.advanced_filter_btn.clicked.connect(lambda: self.open_advanced_filters_requested.emit(self.advanced_filters))
        
        self.scene_filter_combo.currentIndexChanged.connect(self.on_scene_filter_selected)
        self.apply_role_filter_btn.clicked.connect(self.on_apply_role_filter)
        self.clear_role_filter_btn.clicked.connect(self.on_clear_role_filter)

        help_btn.help_requested.connect(self.help_requested)

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

    def update_role_dropdown(self, roles: list):
        self.role_filter_combo.blockSignals(True)
        self.role_filter_combo.clear(); self.role_filter_combo.addItem("-- Select a Role --", -1)
        for role in roles: self.role_filter_combo.addItem(role['name'], role['id'])
        self.role_filter_combo.blockSignals(False)
        self.set_role_filter_enabled(len(roles) > 0)

    def set_standard_filters_enabled(self, enabled: bool):
        self.name_filter_input.setEnabled(enabled)
        self.advanced_filter_btn.setEnabled(enabled)

    def set_role_filter_enabled(self, enabled: bool):
        self.apply_role_filter_btn.setEnabled(enabled)
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
        self.standard_filters_changed.emit(all_filters)
        
    def on_scene_filter_selected(self, index: int):
        scene_id = self.scene_filter_combo.itemData(index) or -1
        self.scene_filter_selected.emit(scene_id)

    def on_apply_role_filter(self):
        scene_id = self.scene_filter_combo.currentData()
        vp_id = self.role_filter_combo.currentData()
        if scene_id > 0 and vp_id > 0:
            self.show_role_info_requested.emit(scene_id, vp_id)

    def on_clear_role_filter(self):
        self.scene_filter_combo.setCurrentIndex(0)
        self.clear_role_info_requested.emit()