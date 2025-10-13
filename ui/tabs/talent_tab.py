import random
from PyQt6.QtCore import Qt, QAbstractListModel, QModelIndex, pyqtSignal, QPoint
from typing import Dict
from PyQt6.QtCore import Qt, QAbstractListModel, QModelIndex, pyqtSignal
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import (
QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
QListView, QGroupBox, QComboBox, QStackedWidget, QSpinBox,
QMessageBox, QScrollArea, QListWidget, QListWidgetItem, QMenu,
QGridLayout
)
from collections import defaultdict

from game_state import Talent, Scene
from ui.dialogs.scene_dialog import SceneDialog
from utils.formatters import format_orientation, format_physical_attribute

class TalentListModel(QAbstractListModel):
    def __init__(self, talents: list = None, parent=None): super().__init__(parent); self.talents = talents or []
    def data(self, index: QModelIndex, role: int):
        if not index.isValid(): return None
        talent = self.talents[index.row()]
        if role == Qt.ItemDataRole.DisplayRole: return talent.alias
        if role == Qt.ItemDataRole.UserRole: return talent
        return None
    def rowCount(self, parent: QModelIndex = QModelIndex()): return len(self.talents)
    def update_data(self, new_talents: list): self.beginResetModel(); self.talents = new_talents; self.endResetModel()

class TalentDetailView(QWidget):
    # Signals to communicate user actions to the presenter
    hire_requested = pyqtSignal(int, list) # talent_id, roles_to_cast
    open_scene_dialog_requested = pyqtSignal(int) # scene_id
    settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_talent = None
        self.setup_ui()
        self.clear_display()
        
    def _open_scene_dialog(self, item: QListWidgetItem):
        role_data = item.data(Qt.ItemDataRole.UserRole)
        if role_data and 'scene_id' in role_data:
            self.open_scene_dialog_requested.emit(role_data['scene_id'])

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(4)
        
        talent_info_group = QGroupBox("Talent Details")
        talent_info_layout = QGridLayout(talent_info_group)
        talent_info_layout.setColumnStretch(0, 1)
        talent_info_layout.setColumnStretch(1, 1)

        self.alias_label = QLabel("<b>Alias:</b> N/A")
        self.age_label = QLabel("<b>Age:</b> N/A")
        self.ethnicity_label = QLabel("<b>Ethnicity:</b> N/A")
        self.orientation_label = QLabel("<b>Orientation:</b> N/A")
        self.physical_label = QLabel("<b>Physical:</b> N/A")
        self.performance_label = QLabel("<b>Performance:</b> N/A")
        self.acting_label = QLabel("<b>Acting:</b> N/A")
        self.stamina_label = QLabel("<b>Stamina:</b> N/A")
        self.popularity_label = QLabel("<b>Popularity:</b> N/A")
        
        talent_info_layout.addWidget(self.alias_label, 0, 0)
        talent_info_layout.addWidget(self.age_label, 1, 0)
        talent_info_layout.addWidget(self.ethnicity_label, 2, 0)
        talent_info_layout.addWidget(self.orientation_label, 3, 0)
        talent_info_layout.addWidget(self.popularity_label, 4, 0)
        
        talent_info_layout.addWidget(self.physical_label, 0, 1)
        talent_info_layout.addWidget(self.performance_label, 1, 1)
        talent_info_layout.addWidget(self.acting_label, 2, 1)
        talent_info_layout.addWidget(self.stamina_label, 3, 1)

        main_layout.addWidget(talent_info_group)
        
        affinities_group = QGroupBox("Tag Affinities"); affinities_group_layout = QVBoxLayout(affinities_group)
        scroll_area = QScrollArea(); scroll_area.setWidgetResizable(True); self.affinities_content_widget = QWidget()
        self.affinities_layout = QVBoxLayout(self.affinities_content_widget); self.affinities_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_area.setWidget(self.affinities_content_widget); affinities_group_layout.addWidget(scroll_area); main_layout.addWidget(affinities_group)

        bottom_container = QWidget(); bottom_layout = QHBoxLayout(bottom_container); bottom_layout.setContentsMargins(0,0,0,0)
        
        # --- Preferences and Limits Section ---
        prefs_limits_group = QGroupBox("Preferences & Limits"); prefs_v_layout = QVBoxLayout(prefs_limits_group)
        prefs_grid_layout = QGridLayout()
        prefs_grid_layout.addWidget(QLabel("<b>Likes</b>:"), 0, 0); prefs_grid_layout.addWidget(QLabel("<b>Dislikes</b>:"), 0, 1)
        self.likes_list = QListWidget(); self.dislikes_list = QListWidget()
        prefs_grid_layout.addWidget(self.likes_list, 1, 0); prefs_grid_layout.addWidget(self.dislikes_list, 1, 1)
        prefs_v_layout.addLayout(prefs_grid_layout)
        
        # New Partner Limits Area
        partner_limits_group = QGroupBox("Partner Limits")
        partner_limits_layout = QGridLayout(partner_limits_group)
        self.max_partners_label = QLabel("<b>Max Scene Partners:</b> N/A")
        self.concurrency_limits_label = QLabel("<b>Concurrency Limits:</b> N/A")
        self.concurrency_limits_label.setWordWrap(True)
        partner_limits_layout.addWidget(self.max_partners_label, 0, 0)
        partner_limits_layout.addWidget(self.concurrency_limits_label, 1, 0)
        partner_limits_layout.setRowStretch(2, 1)
        prefs_v_layout.addWidget(partner_limits_group)
        
        prefs_v_layout.addWidget(QLabel("<b>Hard Limits</b> (Will Refuse Roles):"))
        self.limits_list = QListWidget(); prefs_v_layout.addWidget(self.limits_list)
        bottom_layout.addWidget(prefs_limits_group)

        # --- Policy Section ---
        policy_group = QGroupBox("Contract Requirements"); policy_layout = QVBoxLayout(policy_group)
        policy_layout.addWidget(QLabel("<b>Requires Policies:</b>")); self.requires_policies_list = QListWidget()
        policy_layout.addWidget(self.requires_policies_list); policy_layout.addWidget(QLabel("<b>Refuses Policies:</b>"))
        self.refuses_policies_list = QListWidget(); policy_layout.addWidget(self.refuses_policies_list)
        bottom_layout.addWidget(policy_group); main_layout.addWidget(bottom_container, 1)

        self.contract_container = QGroupBox("Assign to Role"); contract_layout = QVBoxLayout(self.contract_container)
        self.roles_stack = QStackedWidget(); roles_list_widget = QWidget()
        roles_list_layout = QVBoxLayout(roles_list_widget); roles_list_layout.addWidget(QLabel("Available Roles (from scenes in 'casting'):"))
        self.available_roles_list = QListWidget(); self.available_roles_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.available_roles_list.itemDoubleClicked.connect(self._open_scene_dialog)
        roles_list_layout.addWidget(self.available_roles_list)
        roles_no_scenes_widget = QLabel("There are no uncast roles available for this talent."); roles_no_scenes_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        roles_no_scenes_widget.setWordWrap(True); self.roles_stack.addWidget(roles_list_widget); self.roles_stack.addWidget(roles_no_scenes_widget)
        contract_layout.addWidget(self.roles_stack)
        self.hire_button = QPushButton("Assign to Selected Role(s)")
        contract_layout.addWidget(self.hire_button); main_layout.addWidget(self.contract_container)
        self.hire_button.clicked.connect(self.confirm_hire)

    def on_setting_changed(self, key: str):
        if key == "unit_system" and self._selected_talent:
            self.settings_changed.emit()

    def _clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()

    def _populate_preferences_lists(self, talent: Talent, tag_definitions: dict):
        self.likes_list.clear()
        self.dislikes_list.clear()

        likes, dislikes = [], []
        LIKE_THRESHOLD, DISLIKE_THRESHOLD = 1.2, 0.8

        def format_roles(roles_dict: Dict[str, float]) -> str:
            return f"({', '.join([f'{r[0]}: {p:.2f}' for r, p in sorted(roles_dict.items())])})"

        prefs_by_concept = defaultdict(list)
        for tag_name, roles_prefs in talent.tag_preferences.items():
            if not (concept := tag_definitions.get(tag_name, {}).get('concept')):
                concept = tag_name
            prefs_by_concept[concept].append((tag_name, roles_prefs))

        for concept, tags_in_concept in sorted(prefs_by_concept.items()):
            g_scores, r_scores, all_scores = [], [], []
            for _, roles in tags_in_concept:
                if 'Giver' in roles: g_scores.append(roles['Giver'])
                if 'Receiver' in roles: r_scores.append(roles['Receiver'])
                all_scores.extend(roles.values())
            
            if not all_scores: continue
            avg_score = sum(all_scores) / len(all_scores)

            if avg_score >= LIKE_THRESHOLD or avg_score <= DISLIKE_THRESHOLD:
                summary_parts = [concept]
                if g_scores: summary_parts.append(f"G: ~{sum(g_scores)/len(g_scores):.2f}")
                if r_scores: summary_parts.append(f"R: ~{sum(r_scores)/len(r_scores):.2f}")
                summary_line = " ".join(summary_parts)
                
                if avg_score >= LIKE_THRESHOLD:
                    likes.append(summary_line)
                else:
                    dislikes.append(summary_line)
            else:
                for tag_name, roles in tags_in_concept:
                    tag_avg = sum(roles.values()) / len(roles) if roles else 0
                    if tag_avg >= LIKE_THRESHOLD:
                        likes.append(f"{tag_name} {format_roles(roles)}")
                    elif tag_avg <= DISLIKE_THRESHOLD:
                        dislikes.append(f"{tag_name} {format_roles(roles)}")


        if likes: self.likes_list.addItems(sorted(likes))
        else: self.likes_list.addItem("None")

        if dislikes: self.dislikes_list.addItems(sorted(dislikes))
        else: self.dislikes_list.addItem("None")

    def display_talent(self, talent: Talent, available_roles: list, tag_defs: dict, policy_defs: dict):
        if not talent or not hasattr(talent, 'alias') or talent.alias is None: self.clear_display(); return
        self._selected_talent = talent
        self.alias_label.setText(f"<b>Alias:</b> {talent.alias}")
        self.age_label.setText(f"<b>Age:</b> {talent.age}")
        self.ethnicity_label.setText(f"<b>Ethnicity:</b> {talent.ethnicity}")
        self.orientation_label.setText(f"<b>Orientation:</b> {format_orientation(talent.orientation_score, talent.gender)}")
        
        is_visible, physical_text = format_physical_attribute(talent)
        self.physical_label.setVisible(is_visible)
        if is_visible:
            self.physical_label.setText(f"<b>Physical:</b> {physical_text}")
            
        self.performance_label.setText(f"<b>Performance:</b> {talent.performance:.2f}")
        self.acting_label.setText(f"<b>Acting:</b> {talent.acting:.2f}")
        self.stamina_label.setText(f"<b>Stamina:</b> {talent.stamina:.2f}")
        self.popularity_label.setText(f"<b>Popularity:</b> {sum(talent.popularity.values()):.2f}")
        self._clear_layout(self.affinities_layout)
        for tag, affinity in sorted(talent.tag_affinities.items()):
            if affinity > 0: self.affinities_layout.addWidget(QLabel(f"{tag}: {affinity}"))

        self._populate_preferences_lists(talent, tag_defs)
        
        self.max_partners_label.setText(f"<b>Max Scene Partners:</b> {talent.max_scene_partners}")
        if talent.concurrency_limits:
            concurrency_text = ", ".join(f"{k}: {v}" for k, v in sorted(talent.concurrency_limits.items()))
            self.concurrency_limits_label.setText(f"<b>Concurrency Limits:</b> {concurrency_text}")
        else:
            self.concurrency_limits_label.setText("<b>Concurrency Limits:</b> None")

        self.limits_list.clear()
        if talent.hard_limits:
            for limit in sorted(talent.hard_limits):
                item = QListWidgetItem(limit); item.setForeground(QColor("red")); self.limits_list.addItem(item)
        else: self.limits_list.addItem("None")

        self.requires_policies_list.clear(); self.refuses_policies_list.clear()
        policy_names = {p['id']: p['name'] for p in policy_defs.values()}
        if required := talent.policy_requirements.get('requires'): self.requires_policies_list.addItems([policy_names.get(pid, pid) for pid in sorted(required)]);_ = required
        else: self.requires_policies_list.addItem("None")
        if refused := talent.policy_requirements.get('refuses'): self.refuses_policies_list.addItems([policy_names.get(pid, pid) for pid in sorted(refused)]);_ = refused
        else: self.refuses_policies_list.addItem("None")

        self.contract_container.setEnabled(True); self.available_roles_list.clear()

        for role_data in available_roles:
            tags_text = ""
            if tags := role_data.get('tags'):
                tags_to_show = tags[:3]
                if len(tags) > 3: tags_to_show.append("...")
                tags_text = f" (Tags: {', '.join(tags_to_show)})"

            display_text = f"{role_data['scene_title']} - Role: {role_data['vp_name']} (Cost: ${role_data['cost']:,}){tags_text}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, {'scene_id': role_data['scene_id'], 'virtual_performer_id': role_data['virtual_performer_id'], 'cost': role_data['cost']})
            
            if not role_data['is_available']:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled); item.setForeground(QColor("gray"))
                item.setToolTip(f"Unavailable: {role_data['refusal_reason']}")
            elif tags: item.setToolTip(f"Performs: {', '.join(tags)}")
            
            self.available_roles_list.addItem(item)
        
        self.roles_stack.setCurrentIndex(0 if available_roles else 1)
        
    def clear_display(self):
        self._selected_talent = None; self.alias_label.setText("<b>Select a talent from the list</b>")
        self.age_label.setText("<b>Age:</b> N/A"); self.ethnicity_label.setText("<b>Ethnicity:</b> N/A");
        self.orientation_label.setText("<b>Orientation:</b> N/A")
        self.physical_label.setText("<b>Physical:</b> N/A"); self.physical_label.setVisible(True)
        self.performance_label.setText("<b>Performance:</b> N/A"); self.acting_label.setText("<b>Acting:</b> N/A")
        self.stamina_label.setText("<b>Stamina:</b> N/A"); self.popularity_label.setText("<b>Popularity:</b> N/A"); self._clear_layout(self.affinities_layout); self.contract_container.setEnabled(False)
        self.available_roles_list.clear(); self.likes_list.clear(); self.dislikes_list.clear(); self.limits_list.clear()
        self.requires_policies_list.clear(); self.refuses_policies_list.clear()
        self.max_partners_label.setText("<b>Max Scene Partners:</b> N/A")
        self.concurrency_limits_label.setText("<b>Concurrency Limits:</b> N/A")

    def confirm_hire(self):
        if not self._selected_talent: QMessageBox.warning(self, "Error", "No talent selected."); return
        selected_items = self.available_roles_list.selectedItems()
        if not selected_items: QMessageBox.warning(self, "Error", "Please select one or more roles to assign the talent to."); return
        roles_to_cast = []; scene_ids = set()
        for item in selected_items:
            role_data = item.data(Qt.ItemDataRole.UserRole); scene_id = role_data['scene_id']
            if scene_id in scene_ids:
                QMessageBox.warning(self, "Casting Error", f"Cannot cast '{self._selected_talent.alias}' for multiple roles in the same scene.\n\nA talent can only be cast once per scene.")
                return
            scene_ids.add(scene_id); roles_to_cast.append(role_data)
        
        self.hire_requested.emit(self._selected_talent.id, roles_to_cast)
        self.clear_display() 

class HireWindow(QWidget):
    standard_filters_changed = pyqtSignal(dict)
    role_filter_applied = pyqtSignal(int, int)
    role_filter_cleared = pyqtSignal()
    scene_filter_selected = pyqtSignal(int)
    context_menu_requested = pyqtSignal(object, QPoint)
    add_talent_to_category_requested = pyqtSignal(int, int)
    remove_talent_from_category_requested = pyqtSignal(int, int)
    open_advanced_filters_requested = pyqtSignal(dict)
    talent_selected = pyqtSignal(object)
    hire_requested = pyqtSignal(int, list)
    open_scene_dialog_requested = pyqtSignal(int)
    open_talent_profile_requested = pyqtSignal(object)
    initial_load_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.talent_model = TalentListModel()
        self.advanced_filters = {}
        self.setup_ui()
        self.initial_load_requested.emit()

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        left_panel = QWidget(); left_layout = QVBoxLayout(left_panel)
        
        role_filter_group = QGroupBox("Filter for Role"); role_filter_layout = QGridLayout(role_filter_group)
        role_filter_layout.addWidget(QLabel("Scene:"), 0, 0); role_filter_layout.addWidget(QLabel("Role:"), 1, 0)
        self.scene_filter_combo = QComboBox(); self.role_filter_combo = QComboBox()
        role_filter_layout.addWidget(self.scene_filter_combo, 0, 1); role_filter_layout.addWidget(self.role_filter_combo, 1, 1)
        self.apply_role_filter_btn = QPushButton("Apply"); self.clear_role_filter_btn = QPushButton("Clear")
        role_filter_layout.addWidget(self.apply_role_filter_btn, 2, 1); role_filter_layout.addWidget(self.clear_role_filter_btn, 2, 0)
        left_layout.addWidget(role_filter_group)

        self.name_filter_input = QLineEdit(placeholderText="Filter by name...")
        self.advanced_filter_btn = QPushButton("Advanced Filter...")
        left_layout.addWidget(self.name_filter_input); left_layout.addWidget(self.advanced_filter_btn)
        
        self.talent_list_view = QListView(); self.talent_list_view.setModel(self.talent_model)
        left_layout.addWidget(self.talent_list_view)
        
        self.talent_detail_view = TalentDetailView()
        main_layout.addWidget(left_panel, 3); main_layout.addWidget(self.talent_detail_view, 7)

        self.talent_list_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.talent_list_view.customContextMenuRequested.connect(self.show_talent_list_context_menu)
        self.talent_list_view.doubleClicked.connect(self.show_talent_profile)
        self.talent_list_view.selectionModel().currentChanged.connect(self.on_talent_selected)
        
        self.name_filter_input.textChanged.connect(self.filter_talent_list)
        self.advanced_filter_btn.clicked.connect(lambda: self.open_advanced_filters_requested.emit(self.advanced_filters))
        
        self.scene_filter_combo.currentIndexChanged.connect(self.on_scene_filter_selected)
        self.apply_role_filter_btn.clicked.connect(self.on_apply_role_filter)
        self.clear_role_filter_btn.clicked.connect(self.on_clear_role_filter)

        self.talent_detail_view.hire_requested.connect(self.hire_requested)
        self.talent_detail_view.open_scene_dialog_requested.connect(self.open_scene_dialog_requested)
        self.talent_detail_view.settings_changed.connect(self.refresh_from_state)

    def update_talent_list(self, talents: list):
        self.talent_model.update_data(talents)
        if not self.talent_list_view.selectionModel().hasSelection():
            self.talent_detail_view.clear_display()

    def update_scene_dropdown(self, scenes: list):
        self.scene_filter_combo.blockSignals(True)
        current_id = self.scene_filter_combo.currentData()
        self.scene_filter_combo.clear(); self.scene_filter_combo.addItem("-- Select a Scene --", -1)
        for scene in scenes: self.scene_filter_combo.addItem(scene['title'], scene['id'])
        
        idx = self.scene_filter_combo.findData(current_id)
        if idx != -1: self.scene_filter_combo.setCurrentIndex(idx)
        else: self.update_role_dropdown([])
        
        self.scene_filter_combo.blockSignals(False)

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
        index = self.talent_list_view.indexAt(pos)
        if not index.isValid(): return
        if talent := self.talent_model.data(index, Qt.ItemDataRole.UserRole):
            global_pos = self.talent_list_view.viewport().mapToGlobal(pos)
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
        selected_indexes = self.talent_list_view.selectionModel().selectedIndexes()
        if selected_indexes: self.on_talent_selected(selected_indexes[0], QModelIndex())
        else: self.talent_detail_view.clear_display()

    def on_talent_selected(self, current_index, previous_index):
        if not current_index.isValid(): self.talent_detail_view.clear_display(); return
        if talent := self.talent_model.data(current_index, Qt.ItemDataRole.UserRole):
            self.talent_selected.emit(talent)
        else: self.talent_detail_view.clear_display()
        
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
            self.role_filter_applied.emit(scene_id, vp_id)

    def on_clear_role_filter(self):
        self.scene_filter_combo.setCurrentIndex(0)
        self.role_filter_cleared.emit()