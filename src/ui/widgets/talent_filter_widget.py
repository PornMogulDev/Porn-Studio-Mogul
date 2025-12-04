from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QRadioButton, QButtonGroup, QLineEdit,
    QFormLayout, QComboBox, QCheckBox, QPushButton,
    QScrollArea, QFrame
)
from typing import List, Dict

from utils.formatters import inches_to_cm, cm_to_inches
from ui.widgets.talent_filter.categorical_range_filter_widget import CategoricalRangeFilterWidget
from ui.widgets.talent_filter.range_filter_widget import RangeFilterWidget
from ui.widgets.talent_filter.collapsible_group_box import CollapsibleGroupBox
from ui.widgets.talent_filter.checkable_hierarchy_tree_view import CheckableHierarchyTreeView
from ui.widgets.preset_widget import PresetWidget
from ui.presenters.talent_filter_presenter import TalentFilterPresenter

class TalentFilterWidget(QWidget):
    """
    The embedded View for the talent filter. 
    It is a "dumb" component responsible only for displaying data and capturing user input. 
    All actions are delegated to the TalentFilterPresenter.
    """
    # --- Public API and Internal Signals ---
    filters_applied = pyqtSignal(dict)
    apply_requested = pyqtSignal()
    reset_requested = pyqtSignal()
    go_to_toggled = pyqtSignal(bool)
    # Signals for role filtering
    scene_selected = pyqtSignal(int)
    role_selected = pyqtSignal(int, int) # scene_id, vp_id

    def __init__(self, controller, ethnicities_hierarchy: dict, cup_sizes: list, nationalities: list, locations_by_region: dict, go_to_categories: list, current_filters: dict, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        
        self.unit_system = self.settings_manager.get_setting("unit_system", "imperial")
        
        # Store data needed for UI population
        self.ethnicities_hierarchy = ethnicities_hierarchy
        self.locations_by_region = locations_by_region
        self.all_nationalities = nationalities
        self.all_cup_sizes = cup_sizes
        self.cup_size_to_index = {cup: i for i, cup in enumerate(self.all_cup_sizes)}
        self.go_to_categories = go_to_categories
        
        # State for role selection
        self.current_scene_id = None

        self.setup_ui()
        self.connect_signals()

        # Presenter creation
        self.presenter = TalentFilterPresenter(self, controller, current_filters, self.settings_manager)
        self.presenter.load_initial_data()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)

        # 1. PRESETS (Fixed at Top)
        presets_group = CollapsibleGroupBox("Filter Presets")
        presets_layout = QHBoxLayout(presets_group)
        self.preset_widget = PresetWidget()
        presets_layout.addWidget(self.preset_widget)
        main_layout.addWidget(presets_group)

        # 2. SCROLL AREA (Contains all filter groups)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(5, 5, 5, 5)
        self.scroll_layout.setSpacing(10)

        # --- Role Filter ---
        self.role_filter_group = CollapsibleGroupBox("Role Filter")
        role_filter_layout = QVBoxLayout(self.role_filter_group) # Changed to VBox for narrow sidebar
        self.scene_combo = QComboBox()
        self.scene_combo.setPlaceholderText("Filter by Scene...")
        role_filter_layout.addWidget(self.scene_combo)
        
        self.role_combo = QComboBox()
        self.role_combo.setPlaceholderText("Filter by Role...")
        self.role_combo.addItem("Any Role", -1)
        self.role_combo.setEnabled(False)
        role_filter_layout.addWidget(self.role_combo)
        self.scroll_layout.addWidget(self.role_filter_group)
        
        # --- Go-To List ---
        go_to_group = CollapsibleGroupBox("Go-To List Filter")
        go_to_layout = QVBoxLayout(go_to_group)
        self.go_to_only_checkbox = QCheckBox("Show only talent in Go-To Lists")
        go_to_layout.addWidget(self.go_to_only_checkbox)
        self.category_combo = QComboBox()
        self.category_combo.setEnabled(False)
        self.category_combo.addItem("Any", -1)
        for category in sorted(self.go_to_categories, key=lambda c: c['name']):
            self.category_combo.addItem(category['name'], category['id'])
        go_to_layout.addWidget(self.category_combo)
        self.scroll_layout.addWidget(go_to_group)
        
        # --- Gender & Age ---
        self.gender_group = CollapsibleGroupBox("Gender")
        gender_layout = QHBoxLayout(self.gender_group)
        self.gender_any_radio = QRadioButton("Any")
        self.gender_female_radio = QRadioButton("Female")
        self.gender_male_radio = QRadioButton("Male")
        self.gender_button_group = QButtonGroup()
        self.gender_button_group.addButton(self.gender_any_radio)
        self.gender_button_group.addButton(self.gender_female_radio)
        self.gender_button_group.addButton(self.gender_male_radio)
        gender_layout.addWidget(self.gender_any_radio)
        gender_layout.addWidget(self.gender_female_radio)
        gender_layout.addWidget(self.gender_male_radio)
        self.scroll_layout.addWidget(self.gender_group)

        age_group = CollapsibleGroupBox("Age Range")
        age_layout = QVBoxLayout(age_group)
        self.age_range = RangeFilterWidget()
        self.age_range.set_range(18, 99)
        age_layout.addWidget(self.age_range)
        self.scroll_layout.addWidget(age_group)
        
        # --- Skills ---
        skills_group = CollapsibleGroupBox("Core Skills")
        self.skills_layout = QFormLayout(skills_group)
        self.skills_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.perf_range = RangeFilterWidget(); self.perf_range.set_range(0, 100)
        self.act_range = RangeFilterWidget(); self.act_range.set_range(0, 100)
        self.stam_range = RangeFilterWidget(); self.stam_range.set_range(0, 100)
        self.dom_range = RangeFilterWidget(); self.dom_range.set_range(0, 100)
        self.sub_range = RangeFilterWidget(); self.sub_range.set_range(0, 100)
        self.skills_layout.addRow("Perf:", self.perf_range)
        self.skills_layout.addRow("Act:", self.act_range)
        self.skills_layout.addRow("Stam:", self.stam_range)
        self.skills_layout.addRow("Dom:", self.dom_range)
        self.skills_layout.addRow("Sub:", self.sub_range)
        self.scroll_layout.addWidget(skills_group)
        
        # --- Physical ---
        self.phys_group = CollapsibleGroupBox("Physical Attributes")
        self.phys_layout = QFormLayout(self.phys_group)
        self.phys_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.dick_range = RangeFilterWidget()
        self.phys_layout.addRow("Dick Size", self.dick_range)
        self.update_dick_size_filter_ui()
        self.cup_range = CategoricalRangeFilterWidget(self.all_cup_sizes)
        self.phys_layout.addRow("Cup Size:", self.cup_range)
        self.scroll_layout.addWidget(self.phys_group)
        
        # --- Nationality ---
        from PyQt6.QtWidgets import QListWidget
        self.nationality_group = CollapsibleGroupBox("Nationality")
        nationality_layout = QVBoxLayout(self.nationality_group)
        self.nationality_filter_input = QLineEdit()
        self.nationality_filter_input.setPlaceholderText("Filter nationalities...")
        nationality_layout.addWidget(self.nationality_filter_input)
        self.nationality_list = QListWidget()
        self.nationality_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.nationality_list.addItems(sorted(self.all_nationalities))
        self.nationality_list.setFixedHeight(150) # Fixed height for sidebar
        nationality_layout.addWidget(self.nationality_list)
        self.scroll_layout.addWidget(self.nationality_group)

        # --- Location Filters ---
        self.location_group = CollapsibleGroupBox("Location")
        location_main_layout = QVBoxLayout(self.location_group) # Vertical for sidebar
        
        # Base Location
        location_main_layout.addWidget(QLabel("<b>Base Location</b>"))
        self.base_location_tree = CheckableHierarchyTreeView()
        self.base_location_tree.populate_data(self.locations_by_region)
        self.base_location_tree.setFixedHeight(150)
        location_main_layout.addWidget(self.base_location_tree)
        
        # Effective Location
        location_main_layout.addWidget(QLabel("<b>Effective Location</b>"))
        self.effective_location_tree = CheckableHierarchyTreeView()
        self.effective_location_tree.populate_data(self.locations_by_region)
        self.effective_location_tree.setFixedHeight(150)
        location_main_layout.addWidget(self.effective_location_tree)
        
        self.scroll_layout.addWidget(self.location_group)

        # --- Ethnicity ---
        self.ethnicity_group = CollapsibleGroupBox("Ethnicity")
        ethnicity_layout = QVBoxLayout(self.ethnicity_group)
        self.ethnicity_tree = CheckableHierarchyTreeView()
        self.ethnicity_tree.populate_data(self.ethnicities_hierarchy)
        self.ethnicity_tree.setFixedHeight(150)
        ethnicity_layout.addWidget(self.ethnicity_tree)
        self.scroll_layout.addWidget(self.ethnicity_group)

        # Add stretch to push everything up in the scroll view
        self.scroll_layout.addStretch()

        # Set the scroll widget
        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area)
        
        # 3. ACTION BUTTONS (Fixed at Bottom)
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(5, 5, 5, 5)
        
        self.apply_btn = QPushButton("Apply Filters")
        self.apply_btn.setProperty("class", "accent_button") # For styling if needed
        self.apply_btn.clicked.connect(self.apply_requested)
        
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.clicked.connect(self.reset_requested)
        
        button_layout.addWidget(self.apply_btn, 2)
        button_layout.addWidget(self.reset_btn, 1)
        main_layout.addLayout(button_layout)
            
    def connect_signals(self):
        self.go_to_only_checkbox.stateChanged.connect(
            lambda state: self.go_to_toggled.emit(state == Qt.CheckState.Checked.value)
        )
        self.nationality_filter_input.textChanged.connect(self._filter_nationality_list)

        # Connect role filter signals
        self.scene_combo.currentIndexChanged.connect(self._on_scene_changed)
        self.role_combo.currentIndexChanged.connect(self._on_role_changed)

    # --- Scene/Role Signal Handlers ---

    def _on_scene_changed(self, index: int):
        scene_id = self.scene_combo.itemData(index)
        self.current_scene_id = scene_id
        if scene_id is not None:
            self.scene_selected.emit(scene_id)
    
    def _on_role_changed(self, index: int):
        vp_id = self.role_combo.itemData(index)
        if vp_id is not None and self.current_scene_id is not None:
            self.role_selected.emit(self.current_scene_id, vp_id)

    # --- Public methods for the Presenter to command the View ---

    def populate_scenes(self, scenes: List[Dict]):
        self.scene_combo.blockSignals(True)
        self.scene_combo.clear()
        if not scenes:
            self.scene_combo.setEnabled(False)
            self.scene_combo.setPlaceholderText("No Scenes in Casting")
        else:
            self.scene_combo.setEnabled(True)
            self.scene_combo.addItem("Any Scene", -1)
            self.scene_combo.setPlaceholderText("Select Scene...")
            for scene in scenes:
                self.scene_combo.addItem(scene['title'], scene['id'])
        self.scene_combo.setCurrentIndex(0)
        self.scene_combo.blockSignals(False)
    
    def populate_roles(self, roles: List[Dict]):
        self.role_combo.blockSignals(True)
        self.role_combo.clear()
        self.role_combo.setEnabled(bool(roles))
        self.role_combo.addItem("Any Role", -1)
        for role in roles:
            self.role_combo.addItem(role['name'], role['id'])
        self.role_combo.setCurrentIndex(0)
        self.role_combo.blockSignals(False)

    def _set_layout_widgets_enabled(self, layout, enabled: bool):
        """Helper to enable/disable all widgets within a given layout."""
        if layout is None: return
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item and item.widget():
                item.widget().setEnabled(enabled)

    def set_gender_filter_enabled(self, enabled: bool):
        self._set_layout_widgets_enabled(self.gender_group.layout(), enabled)
        if not enabled:
            self.gender_any_radio.setChecked(True)
 
    def set_ethnicity_filter_enabled(self, enabled: bool):
        self._set_layout_widgets_enabled(self.ethnicity_group.layout(), enabled)
        if not enabled:
            self.ethnicity_tree.uncheck_all()

    def set_physical_filters_for_gender(self, gender: str):
        gender_norm = (gender or "any").lower()
        if gender_norm == "male":
            self.dick_range.setEnabled(True)
            self.cup_range.setEnabled(False)
        elif gender_norm == "female":
            self.dick_range.setEnabled(False)
            self.cup_range.setEnabled(True)
        else: # any or switch
            self.dick_range.setEnabled(True)
            self.cup_range.setEnabled(True)

    def update_dick_size_filter_ui(self):
        """Sets the label and range for the dick size filter based on the current unit system."""
        self.unit_system = self.settings_manager.get_setting("unit_system", "imperial")
        label = self.phys_layout.labelForField(self.dick_range)
        if self.unit_system == 'metric':
            if label:
                label.setText("Dick Size (cm):")
            self.dick_range.set_range(inches_to_cm(0), inches_to_cm(20))
        else: # imperial
            if label:
                label.setText("Dick Size (in):")
            self.dick_range.set_range(0, 20)

    def load_filters(self, filters: dict):
        """Loads a given filter dictionary into the UI controls."""
        # Standard controls
        self.go_to_only_checkbox.setChecked(filters.get('go_to_list_only', False))
        index = self.category_combo.findData(filters.get('go_to_category_id', -1))
        if index != -1: self.category_combo.setCurrentIndex(index)
        
        gender = filters.get('gender', 'Any')
        if gender == "Female": self.gender_female_radio.setChecked(True)
        elif gender == "Male": self.gender_male_radio.setChecked(True)
        else: self.gender_any_radio.setChecked(True)
        
        self.age_range.set_values(filters.get('age_min', 18), filters.get('age_max', 99))
        self.perf_range.set_values(filters.get('performance_min', 0), filters.get('performance_max', 100))
        self.act_range.set_values(filters.get('acting_min', 0), filters.get('acting_max', 100))
        self.stam_range.set_values(filters.get('stamina_min', 0), filters.get('stamina_max', 100))
        self.dom_range.set_values(filters.get('dominance_min', 0), filters.get('dominance_max', 100))
        self.sub_range.set_values(filters.get('submission_min', 0), filters.get('submission_max', 100))
        
        selected_cups = filters.get('cup_sizes', [])
        
        # Load dick size
        dick_min_in = filters.get('dick_size_min', 0)
        dick_max_in = filters.get('dick_size_max', 20)
        if self.unit_system == 'metric':
            self.dick_range.set_values(inches_to_cm(dick_min_in), inches_to_cm(dick_max_in))
        else:
            self.dick_range.set_values(round(dick_min_in), round(dick_max_in))

        if not selected_cups:
            min_idx, max_idx = 0, len(self.all_cup_sizes) - 1
        else:
            min_idx = self.cup_size_to_index.get(selected_cups[0], 0)
            max_idx = self.cup_size_to_index.get(selected_cups[-1], len(self.all_cup_sizes) - 1)
        self.cup_range.set_values(min_idx, max_idx)
        
        selected_nationalities = filters.get('nationalities', [])
        for i in range(self.nationality_list.count()):
            self.nationality_list.item(i).setSelected(self.nationality_list.item(i).text() in selected_nationalities)

        # --- Tree View Loading ---
        self.ethnicity_tree.set_checked_items(filters.get('ethnicities', []))
        self.base_location_tree.set_checked_items(filters.get('locations', []))
        self.effective_location_tree.set_checked_items(filters.get('effective_locations', []))

    def gather_current_filters(self) -> dict:
        """Reads all controls and returns the current filter dictionary."""
        filters = {}
        
        # Gather non-conditional filters
        age_min, age_max = self.age_range.get_values()
        perf_min, perf_max = self.perf_range.get_values()
        act_min, act_max = self.act_range.get_values()
        stam_min, stam_max = self.stam_range.get_values()
        dom_min, dom_max = self.dom_range.get_values()
        sub_min, sub_max = self.sub_range.get_values()
        dick_val_min, dick_val_max = self.dick_range.get_values()
        cup_min_idx, cup_max_idx = self.cup_range.get_values()
        
        dick_size_min_in, dick_size_max_in = (cm_to_inches(dick_val_min), cm_to_inches(dick_val_max)) if self.unit_system == 'metric' else (dick_val_min, dick_val_max)

        filters.update({
            'go_to_list_only': self.go_to_only_checkbox.isChecked(),
            'go_to_category_id': self.category_combo.currentData(),
            'age_min': age_min, 'age_max': age_max,
            'performance_min': perf_min, 'performance_max': perf_max,
            'acting_min': act_min, 'acting_max': act_max,
            'stamina_min': stam_min, 'stamina_max': stam_max,
            'dominance_min': dom_min, 'dominance_max': dom_max,
            'submission_min': sub_min, 'submission_max': sub_max,
            'dick_size_min': dick_size_min_in, 'dick_size_max': dick_size_max_in,
            'nationalities': [item.text() for item in self.nationality_list.selectedItems()],
            'locations': self.base_location_tree.get_checked_items(),
            'effective_locations': self.effective_location_tree.get_checked_items(),
        })

        if not (cup_min_idx == 0 and cup_max_idx == len(self.all_cup_sizes) - 1):
            filters['cup_sizes'] = self.all_cup_sizes[cup_min_idx : cup_max_idx + 1]

        # Conditionally add role or general filters
        scene_id = self.scene_combo.currentData()
        vp_id = self.role_combo.currentData()

        if scene_id is not None and vp_id is not None and vp_id > -1:
            filters['scene_id'] = scene_id
            filters['vp_id'] = vp_id
            # Gender and ethnicity are implicitly handled by the role
        else:
            filters['gender'] = 'Female' if self.gender_female_radio.isChecked() else 'Male' if self.gender_male_radio.isChecked() else 'Any'
            filters['ethnicities'] = self.ethnicity_tree.get_checked_items()

        return filters

    def _filter_nationality_list(self, text: str):
        """Hides or shows items in the nationality list based on the filter text."""
        filter_text = text.lower()
        for i in range(self.nationality_list.count()):
            item = self.nationality_list.item(i)
            item_text = item.text().lower()
            item.setHidden(filter_text not in item_text)

    def set_category_combo_enabled(self, is_enabled: bool):
        self.category_combo.setEnabled(is_enabled)
        if not is_enabled: self.category_combo.setCurrentIndex(0)