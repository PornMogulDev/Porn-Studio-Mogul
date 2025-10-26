from PyQt6.QtWidgets import (
QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QDialogButtonBox,
    QFormLayout, QTreeView, QWidget, QScrollArea, QTabWidget, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QListWidget, QListWidgetItem, QGridLayout,
    QMessageBox, QStackedWidget, QPushButton
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QColor
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot

from data.game_state import Talent, Scene
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin
from utils.formatters import format_orientation, format_physical_attribute, CHEMISTRY_MAP

class TalentProfileDialog(GeometryManagerMixin, QDialog):
    # Signals for the Presenter
    hire_confirmed = pyqtSignal(list)  # roles_to_cast
    open_scene_dialog_requested = pyqtSignal(int)  # scene_id
    talent_profile_requested = pyqtSignal(int)  # other_talent_id

    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.presenter = None  # Will be set by UIManager
            
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMinimumSize(800, 600)

        self.setup_ui()
        self._connect_signals()
        self._restore_geometry()

    def update_window_title(self, alias: str):
        self.setWindowTitle(f"Talent Profile: {alias}")

    def _create_profile_tab(self):
        profile_tab = QWidget()
        layout = QHBoxLayout(profile_tab)
            
        widget_for_layout = QWidget()
        left_layout = QVBoxLayout(widget_for_layout)
    
        layout.addWidget(widget_for_layout, 1)
 
        details_group = QGroupBox("Details")
        details_layout = QFormLayout(details_group)
        self.age_label = QLabel()
        self.ethnicity_label = QLabel()
        self.gender_label = QLabel()
        self.orientation_label = QLabel()
        self.popularity_label = QLabel()
        self.physical_attr_name_label = QLabel()
        self.physical_attr_value_label = QLabel()
        details_layout.addRow("<b>Age:</b>", self.age_label)
        details_layout.addRow("<b>Gender:</b>", self.gender_label)
        details_layout.addRow("<b>Orientation:</b>", self.orientation_label)
        details_layout.addRow("<b>Ethnicity:</b>", self.ethnicity_label)
        details_layout.addRow(self.physical_attr_name_label, self.physical_attr_value_label)
        left_layout.addWidget(details_group)
        details_layout.addRow("<b>Popularity:</b>", self.popularity_label)

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

        left_layout.addStretch()
        layout.addStretch(1)
        
        return profile_tab

    def _create_history_chem_tabs(self, main_tab_widget: QTabWidget):
        
        history_tab = QWidget()
        history_tab_layout = QVBoxLayout(history_tab)
        history_group = QGroupBox("Scene History")
        history_layout = QVBoxLayout(history_group)
        self.scene_history_tree = QTreeView()
        self.scene_history_model = QStandardItemModel()
        self.scene_history_tree.setModel(self.scene_history_model)
        self.scene_history_tree.setHeaderHidden(True)
        self.scene_history_tree.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self.scene_history_tree.doubleClicked.connect(self._on_role_double_clicked)
        history_layout.addWidget(self.scene_history_tree)
        history_tab_layout.addWidget(history_group)
        history_tab.setLayout(history_tab_layout)

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
        self.chemistry_table.itemDoubleClicked.connect(self._on_chemistry_double_clicked)
        chemistry_layout.addWidget(self.chemistry_table)
        chemistry_tab_layout.addWidget(chemistry_group)
        chemistry_tab.setLayout(chemistry_tab_layout)

        main_tab_widget.addTab(history_tab, "Scene History")
        main_tab_widget.addTab(chemistry_tab, "Chemistry")

    def _create_prefs_tab(self):
        
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
    
        return prefs_tab

    def _create_hiring_tab(self):
        hiring_tab = QWidget()
        layout = QVBoxLayout(hiring_tab)

        self.contract_container = QGroupBox("Assign to Role")
        contract_layout = QVBoxLayout(self.contract_container)
        self.roles_stack = QStackedWidget()
        roles_list_widget = QWidget()
        roles_list_layout = QVBoxLayout(roles_list_widget)
        roles_list_layout.addWidget(QLabel("Available Roles (from scenes in 'casting'):"))
        self.available_roles_list = QListWidget()
        self.available_roles_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.available_roles_list.itemDoubleClicked.connect(self._on_role_double_clicked)
        roles_list_layout.addWidget(self.available_roles_list)
        
        roles_no_scenes_widget = QLabel("There are no uncast roles available for this talent.")
        roles_no_scenes_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        roles_no_scenes_widget.setWordWrap(True)
        
        self.roles_stack.addWidget(roles_list_widget)
        self.roles_stack.addWidget(roles_no_scenes_widget)
        contract_layout.addWidget(self.roles_stack)
        
        self.hire_button = QPushButton("Assign Talent to Selected Role(s)")
        self.hire_button.clicked.connect(self._confirm_hire)
        contract_layout.addWidget(self.hire_button)
        
        layout.addWidget(self.contract_container)
        return hiring_tab

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        tab_widget = QTabWidget()

        tab_widget.addTab(self._create_profile_tab(), "Profile")
        tab_widget.addTab(self._create_prefs_tab(), "Preferences & Requirements")
        self._create_history_chem_tabs(tab_widget)
        tab_widget.addTab(self._create_hiring_tab(), "Hiring")

        main_layout.addWidget(tab_widget)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def _connect_signals(self):
        pass
        
    def populate_physical_label(self, talent: Talent):
        unit_system = self.settings_manager.get_setting("unit_system", "imperial")
        attr_name, attr_value = format_physical_attribute(talent, unit_system)
        
        if attr_name:
            self.physical_attr_name_label.setText(f"<b>{attr_name}:</b>")
            self.physical_attr_value_label.setText(attr_value)
            self.physical_attr_name_label.setVisible(True)
            self.physical_attr_value_label.setVisible(True)
        else:
            self.physical_attr_name_label.setVisible(False)
            self.physical_attr_value_label.setVisible(False)

    # --- Public Methods for Presenter ---
    def display_basic_info(self, data: dict):
            self.age_label.setText(str(data['age']))
            self.gender_label.setText(data['gender'])
            self.orientation_label.setText(format_orientation(data['orientation'], data['gender']))
            self.ethnicity_label.setText(data['ethnicity'])
            self.popularity_label.setText(f"{data['popularity']:.2f}")
            
    def display_skills(self, data: dict):
            self.performance_label.setText(f"{data['performance']:.2f}")
            self.acting_label.setText(f"{data['acting']:.2f}")
            self.stamina_label.setText(f"{data['stamina']:.2f}")
            self.ambition_label.setText(str(data['ambition']))
            self.professionalism_label.setText(str(data['professionalism']))
    
    def display_affinities(self, affinities: list):
            while self.affinities_layout.count():
                self.affinities_layout.takeAt(0).widget().deleteLater()
            for tag, affinity in affinities:
                self.affinities_layout.addWidget(QLabel(f"{tag}: {affinity}"))

    def display_preferences(self, likes: list, dislikes: list, limits: list, required_policies: list, refused_policies: list):
        self.likes_list.clear()
        if likes: self.likes_list.addItems(likes)
        else: self.likes_list.addItem("None")
                
        self.dislikes_list.clear()
        if dislikes: self.dislikes_list.addItems(dislikes)
        else: self.dislikes_list.addItem("None")

        self.limits_list.clear()
        if limits:
            for limit in limits:
                item = QListWidgetItem(limit)
                item.setForeground(QColor("red"))
                self.limits_list.addItem(item)
        else:
            self.limits_list.addItem("None")
 
        self.requires_policies_list.clear()
        if required_policies:
            self.requires_policies_list.addItems(required_policies)
        else: self.requires_policies_list.addItem("None")
         
        self.refuses_policies_list.clear()
        if refused_policies:
            self.refuses_policies_list.addItems(refused_policies)
        else: self.refuses_policies_list.addItem("None")
    
    def update_available_roles(self, available_roles: list):
        """
        Populates the available roles list from data provided by the presenter.
        """
        self.available_roles_list.clear()

        if not available_roles:
            self.roles_stack.setCurrentIndex(1)
            return

        self.roles_stack.setCurrentIndex(0)
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
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                item.setForeground(QColor("gray"))
                item.setToolTip(f"Unavailable: {role_data['refusal_reason']}")
            elif tags:
                item.setToolTip(f"Performs: {', '.join(tags)}")
            
            self.available_roles_list.addItem(item)

    def _on_role_double_clicked(self, item: QListWidgetItem):
        if role_data := item.data(Qt.ItemDataRole.UserRole):
            self.open_scene_dialog_requested.emit(role_data['scene_id'])

    def _confirm_hire(self):
        selected_items = self.available_roles_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Roles Selected", "Please select one or more roles to assign the talent to.")
            return
        
        roles_to_cast, scene_ids, current_alias = [], set(), self.windowTitle().replace("Talent Profile: ", "")
        for item in selected_items:
            role_data = item.data(Qt.ItemDataRole.UserRole)
            if role_data['scene_id'] in scene_ids:
                QMessageBox.warning(self, "Casting Error", f"Cannot cast '{current_alias}' for multiple roles in the same scene.\nA talent can only be cast once per scene.")
                return
            scene_ids.add(role_data['scene_id'])
            roles_to_cast.append(role_data)
        self.hire_confirmed.emit(roles_to_cast)

    def _on_chemistry_double_clicked(self, item: QTableWidgetItem):
        # We only care about clicks in the first column (talent alias)
        if item.column() == 0:
            if talent_id := self.chemistry_table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole):
                self.talent_profile_requested.emit(talent_id)
 
    def display_chemistry(self, chemistry_data: list):
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
            
    def display_scene_history(self, scene_history: list[Scene]):
        self.scene_history_model.clear()
        root_node = self.scene_history_model.invisibleRootItem()
    
        if not scene_history:
            root_node.appendRow(QStandardItem("No scenes on record."))
            return

        for scene in scene_history:
            scene_item = QStandardItem(f"{scene.title} ({scene.display_status})")
            font = scene_item.font()
            font.setBold(True)
            scene_item.setFont(font)
            scene_item.setEditable(False)

            contributions = [c for c in scene.performer_contributions if c.talent_id == self.presenter.talent.id]
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