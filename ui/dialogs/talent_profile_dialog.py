from PyQt6.QtWidgets import (
QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QDialogButtonBox,
QFormLayout, QTreeView, QSplitter, QWidget, QScrollArea, QTabWidget, QTableWidget, QTableWidgetItem, QAbstractItemView,
QListWidget, QListWidgetItem, QGridLayout
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QColor
from PyQt6.QtCore import Qt
from collections import defaultdict

from game_state import Talent
from game_controller import GameController
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin
from utils.formatters import format_orientation, format_physical_attribute, CHEMISTRY_MAP

class TalentProfileDialog(GeometryManagerMixin, QDialog):
    def __init__(self, talent: Talent, controller: GameController, parent=None):
        super().__init__(parent)
        self.talent = talent
        self.controller = controller
        self.settings_manager = self.controller.settings_manager
            
        self.setWindowTitle(f"Talent Profile: {self.talent.alias}")
        self.setMinimumSize(800, 600)

        self.setup_ui()
        self.populate_data()
        self.controller.settings_manager.signals.setting_changed.connect(self.on_setting_changed)
        self._restore_geometry()

    def on_setting_changed(self, key: str):
        if key == "unit_system":
            self.populate_physical_label()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        details_group = QGroupBox("Details")
        details_layout = QFormLayout(details_group)
        self.age_label = QLabel()
        self.ethnicity_label = QLabel()
        self.gender_label = QLabel()
        self.orientation_label = QLabel()
        self.physical_label = QLabel()
        details_layout.addRow("<b>Age:</b>", self.age_label)
        details_layout.addRow("<b>Gender:</b>", self.gender_label)
        details_layout.addRow("<b>Orientation:</b>", self.orientation_label)
        details_layout.addRow("<b>Ethnicity:</b>", self.ethnicity_label)
        details_layout.addRow("<b>Physical:</b>", self.physical_label)
        left_layout.addWidget(details_group)

        skills_group = QGroupBox("Skills & Attributes")
        skills_layout = QFormLayout(skills_group)
        self.performance_label = QLabel()
        self.acting_label = QLabel()
        self.stamina_label = QLabel()
        self.ambition_label = QLabel()
        self.professionalism_label = QLabel()
        skills_layout.addRow("<b>Performance:</b>", self.performance_label)
        skills_layout.addRow("<b>Acting:</b>", self.acting_label)
        skills_layout.addRow("<b>Stamina:</b>", self.stamina_label)
        skills_layout.addRow("<b>Ambition:</b>", self.ambition_label)
        skills_layout.addRow("<b>Professionalism:</b>", self.professionalism_label)
        left_layout.addWidget(skills_group)

        affinities_group = QGroupBox("Tag Affinities")
        affinities_layout = QVBoxLayout(affinities_group)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        self.affinities_content_widget = QWidget()
        self.affinities_layout = QVBoxLayout(self.affinities_content_widget)
        self.affinities_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_area.setWidget(self.affinities_content_widget)
        affinities_layout.addWidget(scroll_area)
        left_layout.addWidget(affinities_group, 1)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.right_tabs = QTabWidget()
        
        history_tab = QWidget()
        history_tab_layout = QVBoxLayout(history_tab)
        history_group = QGroupBox("Scene History")
        history_layout = QVBoxLayout(history_group)
        self.scene_history_tree = QTreeView()
        self.scene_history_model = QStandardItemModel()
        self.scene_history_tree.setModel(self.scene_history_model)
        self.scene_history_tree.setHeaderHidden(True)
        self.scene_history_tree.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        history_layout.addWidget(self.scene_history_tree)
        history_tab_layout.addWidget(history_group)
        self.right_tabs.addTab(history_tab, "Scene History")

        chemistry_tab = QWidget()
        chemistry_tab_layout = QVBoxLayout(chemistry_tab)
        chemistry_group = QGroupBox("Chemistry")
        chemistry_layout = QVBoxLayout(chemistry_group)
        self.chemistry_table = QTableWidget()
        self.chemistry_table.setColumnCount(2)
        self.chemistry_table.setHorizontalHeaderLabels(["Talent", "Chemistry"])
        self.chemistry_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.chemistry_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.chemistry_table.verticalHeader().setVisible(False)
        self.chemistry_table.horizontalHeader().setStretchLastSection(True)
        chemistry_layout.addWidget(self.chemistry_table)
        chemistry_tab_layout.addWidget(chemistry_group)
        self.right_tabs.addTab(chemistry_tab, "Chemistry")
        
        prefs_tab = QWidget()
        prefs_tab_layout = QHBoxLayout(prefs_tab)
        
        prefs_limits_group = QGroupBox("Preferences & Limits")
        prefs_grid_layout = QGridLayout(prefs_limits_group)
        prefs_grid_layout.addWidget(QLabel("<b>Likes</b> (Reduces Hire Cost):"), 0, 0)
        prefs_grid_layout.addWidget(QLabel("<b>Dislikes</b> (Increases Hire Cost):"), 0, 1)
        self.likes_list = QListWidget(); self.dislikes_list = QListWidget()
        prefs_grid_layout.addWidget(self.likes_list, 1, 0); prefs_grid_layout.addWidget(self.dislikes_list, 1, 1)
        prefs_grid_layout.addWidget(QLabel("<b>Hard Limits</b> (Will Refuse Roles):"), 2, 0, 1, 2)
        self.limits_list = QListWidget()
        prefs_grid_layout.addWidget(self.limits_list, 3, 0, 1, 2)
        prefs_tab_layout.addWidget(prefs_limits_group)
        
        policy_group = QGroupBox("Contract Requirements")
        policy_layout = QVBoxLayout(policy_group)
        policy_layout.addWidget(QLabel("<b>Requires Policies:</b>"))
        self.requires_policies_list = QListWidget()
        policy_layout.addWidget(self.requires_policies_list)
        policy_layout.addWidget(QLabel("<b>Refuses Policies:</b>"))
        self.refuses_policies_list = QListWidget()
        policy_layout.addWidget(self.refuses_policies_list)
        prefs_tab_layout.addWidget(policy_group)
        
        self.right_tabs.addTab(prefs_tab, "Preferences & Requirements")
        
        right_layout.addWidget(self.right_tabs)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        main_layout.addWidget(splitter)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def update_with_talent(self, talent: Talent):
        """Clears and repopulates the entire dialog with data from a new talent."""
        self.talent = talent
        self.setWindowTitle(f"Talent Profile: {self.talent.alias}")
        self.populate_data()
        
    def populate_physical_label(self):
        is_visible, physical_text = format_physical_attribute(self.talent)
        self.physical_label.setText(physical_text if is_visible else "N/A")

    def populate_data(self):
        self.age_label.setText(str(self.talent.age))
        self.gender_label.setText(self.talent.gender)
        self.orientation_label.setText(format_orientation(self.talent.orientation_score, self.talent.gender))
        self.ethnicity_label.setText(self.talent.ethnicity)
        self.populate_physical_label()

        self.performance_label.setText(f"{self.talent.performance:.2f}")
        self.acting_label.setText(f"{self.talent.acting:.2f}")
        self.stamina_label.setText(f"{self.talent.stamina:.2f}")
        self.ambition_label.setText(str(self.talent.ambition))
        self.professionalism_label.setText(str(self.talent.professionalism))
        
        for tag, affinity in sorted(self.talent.tag_affinities.items()):
            if affinity > 0:
                self.affinities_layout.addWidget(QLabel(f"{tag}: {affinity}"))

        self.populate_scene_history()
        self.populate_chemistry()
        self.populate_preferences()

    def _populate_preferences_lists(self):
        tag_definitions = self.controller.data_manager.tag_definitions
        
        avg_prefs_by_tag = {
            tag: sum(roles.values()) / len(roles)
            for tag, roles in self.talent.tag_preferences.items() if roles
        }
        
        prefs_by_orientation = defaultdict(dict)
        prefs_by_concept = defaultdict(dict)
        
        for tag, avg_score in avg_prefs_by_tag.items():
            tag_def = tag_definitions.get(tag)
            if not tag_def: continue
            
            if orientation := tag_def.get('orientation'):
                prefs_by_orientation[orientation][tag] = avg_score
            if concept := tag_def.get('concept'):
                prefs_by_concept[concept][tag] = avg_score

        likes, dislikes, processed_tags = [], [], set()
        DISLIKE_THRESHOLD, LIKE_THRESHOLD, EXCEPTION_DEVIATION = 0.8, 1.2, 0.2

        for orientation, tags_with_scores in prefs_by_orientation.items():
            scores = list(tags_with_scores.values())
            if scores and all(score < DISLIKE_THRESHOLD for score in scores):
                dislikes.append(f"{orientation} scenes")
                processed_tags.update(tags_with_scores.keys())

        for concept, tags_with_scores in prefs_by_concept.items():
            unprocessed = {tag: score for tag, score in tags_with_scores.items() if tag not in processed_tags}
            if not unprocessed: continue
            
            scores = list(unprocessed.values())
            avg_score = sum(scores) / len(scores)
            is_like, is_dislike = avg_score >= LIKE_THRESHOLD, avg_score <= DISLIKE_THRESHOLD
            
            if is_like or is_dislike:
                summary = f"{concept} scenes (~{avg_score:.2f})"; (likes if is_like else dislikes).append(summary)
                for tag, score in unprocessed.items():
                    if abs(score - avg_score) > EXCEPTION_DEVIATION:
                        roles = ", ".join([f"{r}: {p:.2f}" for r, p in sorted(self.talent.tag_preferences[tag].items())])
                        exception = f"  • Except: {tag} ({roles})"; (likes if score > avg_score else dislikes).append(exception)
                processed_tags.update(unprocessed.keys())

        for tag, avg_score in avg_prefs_by_tag.items():
            if tag in processed_tags: continue
            if avg_score >= LIKE_THRESHOLD or avg_score <= DISLIKE_THRESHOLD:
                roles = ", ".join([f"{r}: {p:.2f}" for r, p in sorted(self.talent.tag_preferences[tag].items())])
                display = f"{tag} ({roles})"; (likes if avg_score >= LIKE_THRESHOLD else dislikes).append(display)

        self.likes_list.clear(); self.dislikes_list.clear()
        if likes: self.likes_list.addItems(sorted(likes))
        else: self.likes_list.addItem("None")
        if dislikes: self.dislikes_list.addItems(sorted(dislikes))
        else: self.dislikes_list.addItem("None")

    def populate_preferences(self):
        self._populate_preferences_lists()
        
        self.limits_list.clear()
        if self.talent.hard_limits:
            for limit in sorted(self.talent.hard_limits):
                item = QListWidgetItem(limit)
                item.setForeground(QColor("red"))
                self.limits_list.addItem(item)
        else:
            self.limits_list.addItem("None")

        self.requires_policies_list.clear(); self.refuses_policies_list.clear()
        policy_names = {p['id']: p['name'] for p in self.controller.data_manager.on_set_policies_data.values()}
        
        if required := self.talent.policy_requirements.get('requires'):
            self.requires_policies_list.addItems([policy_names.get(pid, pid) for pid in sorted(required)])
        else: self.requires_policies_list.addItem("None")
        
        if refused := self.talent.policy_requirements.get('refuses'):
            self.refuses_policies_list.addItems([policy_names.get(pid, pid) for pid in sorted(refused)])
        else: self.refuses_policies_list.addItem("None")

    def populate_chemistry(self):
        self.chemistry_table.setRowCount(0)
        chemistry_data = self.controller.talent_service.get_talent_chemistry(self.talent.id)

        self.chemistry_table.setRowCount(len(chemistry_data))
        for row, chem_info in enumerate(chemistry_data):
            score = chem_info['score']
            display_text, color = CHEMISTRY_MAP.get(score, ("Unknown", QColor("black")))
            
            alias_item = QTableWidgetItem(chem_info['other_talent_alias'])
            alias_item.setData(Qt.ItemDataRole.UserRole, chem_info['other_talent_id'])

            chem_item = QTableWidgetItem(display_text)
            chem_item.setForeground(color)
            chem_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.chemistry_table.setItem(row, 0, alias_item)
            self.chemistry_table.setItem(row, 1, chem_item)
        
        self.chemistry_table.resizeColumnsToContents()
            
    def populate_scene_history(self):
        self.scene_history_model.clear()
        root_node = self.scene_history_model.invisibleRootItem()
        
        scene_history = self.controller.get_scene_history_for_talent(self.talent.id)
        
        if not scene_history:
            root_node.appendRow(QStandardItem("No scenes on record."))
            return

        for scene in scene_history:
            scene_item = QStandardItem(f"{scene.title} ({scene.display_status})")
            font = scene_item.font()
            font.setBold(True)
            scene_item.setFont(font)
            scene_item.setEditable(False)

            contributions = [c for c in scene.performer_contributions if c.talent_id == self.talent.id]
            if contributions:
                sorted_contributions = sorted(contributions, key=lambda c: c.contribution_key)
                for contrib in sorted_contributions:
                    contrib_item = QStandardItem(f"  • {contrib.contribution_key}: {contrib.quality_score:.2f} quality")
                    contrib_item.setEditable(False)
                    scene_item.appendRow(contrib_item)
            else:
                contrib_item = QStandardItem("  • Role data not available.")
                contrib_item.setEditable(False)
                scene_item.appendRow(contrib_item)

            root_node.appendRow(scene_item)
            
        self.scene_history_tree.expandAll()