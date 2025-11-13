from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QRadioButton, QButtonGroup, QLineEdit,
    QFormLayout, QComboBox, QCheckBox, QDialogButtonBox,
    QMessageBox
)

from utils.formatters import inches_to_cm, cm_to_inches
from ui.widgets.talent_filter.categorical_range_filter_widget import CategoricalRangeFilterWidget
from ui.widgets.talent_filter.collapsible_group_box import CollapsibleGroupBox
from ui.widgets.talent_filter.checkable_hierarchy_tree_view import CheckableHierarchyTreeView
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin
from ui.presenters.talent_filter_presenter import TalentFilterPresenter

class TalentFilterDialog(GeometryManagerMixin, QDialog):
    # --- Public API and Internal Signals ---
    filters_applied = pyqtSignal(dict)
    apply_requested = pyqtSignal()
    reset_requested = pyqtSignal()
    apply_and_close_requested = pyqtSignal()
    go_to_toggled = pyqtSignal(bool)

    def __init__(self, ethnicities_hierarchy: dict, cup_sizes: list, nationalities: list, locations_by_region: dict, go_to_categories: list, current_filters: dict, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.unit_system = self.settings_manager.get_setting("unit_system", "imperial")
        self.setWindowTitle("Advanced Talent Filter")
        self.defaultSize = QSize(700, 1000)

        # Store data needed for UI population
        self.ethnicities_hierarchy = ethnicities_hierarchy
        self.locations_by_region = locations_by_region
        self.all_nationalities = nationalities
        self.all_cup_sizes = cup_sizes
        self.cup_size_to_index = {cup: i for i, cup in enumerate(self.all_cup_sizes)}
        self.go_to_categories = go_to_categories

        self.setup_ui()
        self._populate_presets_combobox()
        self.settings_manager.signals.setting_changed.connect(self._on_setting_changed)
        self.connect_signals()

        self.presenter = TalentFilterPresenter(self, current_filters)
        self.presenter.load_initial_data()

        self._restore_geometry()
    
    def _populate_presets_combobox(self):
        current_text = self.preset_combo.currentText()
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        presets = self.settings_manager.get_talent_filter_presets()
        if presets:
            self.preset_combo.addItems(sorted(presets.keys()))
        
        index = self.preset_combo.findText(current_text)
        if index != -1: self.preset_combo.setCurrentIndex(index)
        else: self.preset_combo.setCurrentIndex(-1)
        self.preset_combo.blockSignals(False)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        from ui.widgets.talent_filter.range_filter_widget import RangeFilterWidget

        presets_group = CollapsibleGroupBox("Filter Presets"); presets_layout = QHBoxLayout(presets_group); presets_layout.addWidget(QLabel("Preset:")); self.preset_combo = QComboBox(); self.preset_combo.setEditable(True); self.preset_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert); self.preset_combo.setToolTip("Select a saved preset or type a new name to save."); presets_layout.addWidget(self.preset_combo); self.load_preset_button = QPushButton("Load"); presets_layout.addWidget(self.load_preset_button); self.save_preset_button = QPushButton("Save"); presets_layout.addWidget(self.save_preset_button); self.delete_preset_button = QPushButton("Delete"); presets_layout.addWidget(self.delete_preset_button); main_layout.addWidget(presets_group)
        go_to_group = CollapsibleGroupBox("Go-To List Filter"); go_to_layout = QVBoxLayout(go_to_group); self.go_to_only_checkbox = QCheckBox("Show only talent in Go-To Lists"); go_to_layout.addWidget(self.go_to_only_checkbox); self.category_combo = QComboBox(); self.category_combo.setEnabled(False); self.category_combo.addItem("Any", -1);
        for category in sorted(self.go_to_categories, key=lambda c: c['name']): self.category_combo.addItem(category['name'], category['id'])
        go_to_layout.addWidget(self.category_combo); main_layout.addWidget(go_to_group)
        gender_group = CollapsibleGroupBox("Gender"); gender_layout = QHBoxLayout(gender_group); self.gender_any_radio = QRadioButton("Any"); self.gender_female_radio = QRadioButton("Female"); self.gender_male_radio = QRadioButton("Male"); self.gender_button_group = QButtonGroup(); self.gender_button_group.addButton(self.gender_any_radio); self.gender_button_group.addButton(self.gender_female_radio); self.gender_button_group.addButton(self.gender_male_radio); gender_layout.addWidget(self.gender_any_radio); gender_layout.addWidget(self.gender_female_radio); gender_layout.addWidget(self.gender_male_radio); main_layout.addWidget(gender_group)
        age_group = CollapsibleGroupBox("Age Range"); age_layout = QVBoxLayout(age_group); self.age_range = RangeFilterWidget(); self.age_range.set_range(18, 99); age_layout.addWidget(self.age_range); main_layout.addWidget(age_group)
        skills_group = CollapsibleGroupBox("Core Skills"); self.skills_layout = QFormLayout(skills_group); self.perf_range = RangeFilterWidget(); self.perf_range.set_range(0, 100); self.act_range = RangeFilterWidget(); self.act_range.set_range(0, 100); self.stam_range = RangeFilterWidget(); self.stam_range.set_range(0, 100); self.dom_range = RangeFilterWidget(); self.dom_range.set_range(0, 100); self.sub_range = RangeFilterWidget(); self.sub_range.set_range(0, 100); self.skills_layout.addRow("Performance:", self.perf_range); self.skills_layout.addRow("Acting:", self.act_range); self.skills_layout.addRow("Stamina:", self.stam_range); self.skills_layout.addRow("Dominance:", self.dom_range); self.skills_layout.addRow("Submission:", self.sub_range); main_layout.addWidget(skills_group)
        phys_group = CollapsibleGroupBox("Physical Attributes"); self.phys_layout = QFormLayout(phys_group); self.dick_range = RangeFilterWidget(); self.phys_layout.addRow("Dick Size", self.dick_range);
        self._update_dick_size_filter_ui()
        self.cup_range = CategoricalRangeFilterWidget(self.all_cup_sizes); self.phys_layout.addRow("Cup Size:", self.cup_range); main_layout.addWidget(phys_group)
        
        from PyQt6.QtWidgets import QListWidget # Import locally for nationality
        nationality_group = CollapsibleGroupBox("Nationality"); nationality_layout = QVBoxLayout(nationality_group); self.nationality_filter_input = QLineEdit(); self.nationality_filter_input.setPlaceholderText("Filter nationalities..."); nationality_layout.addWidget(self.nationality_filter_input); self.nationality_list = QListWidget(); self.nationality_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection); self.nationality_list.addItems(sorted(self.all_nationalities)); nationality_layout.addWidget(self.nationality_list); main_layout.addWidget(nationality_group)

        # --- Tree View Setup ---
        location_group = CollapsibleGroupBox("Location")
        location_layout = QVBoxLayout(location_group)
        self.location_tree = CheckableHierarchyTreeView()
        self.location_tree.populate_data(self.locations_by_region)
        location_layout.addWidget(self.location_tree)
        main_layout.addWidget(location_group)

        ethnicity_group = CollapsibleGroupBox("Ethnicity")
        ethnicity_layout = QVBoxLayout(ethnicity_group)
        self.ethnicity_tree = CheckableHierarchyTreeView()
        self.ethnicity_tree.populate_data(self.ethnicities_hierarchy)
        ethnicity_layout.addWidget(self.ethnicity_tree)
        main_layout.addWidget(ethnicity_group)

        # Stretch factors and buttons
        main_layout.setStretchFactor(nationality_group, 3); main_layout.setStretchFactor(location_group, 4); main_layout.setStretchFactor(ethnicity_group, 4)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Reset | QDialogButtonBox.StandardButton.Close)
        button_box.button(QDialogButtonBox.StandardButton.Ok).clicked.connect(self.apply_and_close_requested)
        button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply_requested)
        button_box.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(self.reset_requested)
        button_box.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.reject)
        main_layout.addWidget(button_box)

    def _on_setting_changed(self, key: str):
        """Handles live updates if the unit system is changed while the dialog is open."""
        if key == 'unit_system':
            self.unit_system = self.settings_manager.get_setting("unit_system", "imperial")
            # 1. Get current filter values, standardized to inches
            current_filters = self.gather_current_filters()
            # 2. Update the UI's label and range for the new unit system
            self._update_dick_size_filter_ui()
            # 3. Reload the standardized inch values, which will be converted to the new UI unit
            self.load_filters(current_filters)
            
    def _update_dick_size_filter_ui(self):
        """Sets the label and range for the dick size filter based on the current unit system."""
        label = self.phys_layout.labelForField(self.dick_range)
        if self.unit_system == 'metric':
            if label:
                label.setText("Dick Size (cm):")
            self.dick_range.set_range(inches_to_cm(0), inches_to_cm(20))
        else: # imperial
            if label:
                label.setText("Dick Size (in):")
            self.dick_range.set_range(0, 20)

    def connect_signals(self):
        self.go_to_only_checkbox.stateChanged.connect(
            lambda state: self.go_to_toggled.emit(state == Qt.CheckState.Checked.value)
        )
        self.load_preset_button.clicked.connect(self._on_load_preset_clicked)
        self.save_preset_button.clicked.connect(self._on_save_preset_clicked)
        self.delete_preset_button.clicked.connect(self._on_delete_preset_clicked)
        self.nationality_filter_input.textChanged.connect(self._filter_nationality_list)

    def load_filters(self, filters: dict):
        """Loads a given filter dictionary into the UI controls."""
        # Standard controls
        self.go_to_only_checkbox.setChecked(filters.get('go_to_list_only', False)); index = self.category_combo.findData(filters.get('go_to_category_id', -1));
        if index != -1: self.category_combo.setCurrentIndex(index)
        gender = filters.get('gender', 'Any');
        if gender == "Female": self.gender_female_radio.setChecked(True)
        elif gender == "Male": self.gender_male_radio.setChecked(True)
        else: self.gender_any_radio.setChecked(True)
        self.age_range.set_values(filters.get('age_min', 18), filters.get('age_max', 99)); self.perf_range.set_values(filters.get('performance_min', 0), filters.get('performance_max', 100)); self.act_range.set_values(filters.get('acting_min', 0), filters.get('acting_max', 100)); self.stam_range.set_values(filters.get('stamina_min', 0), filters.get('stamina_max', 100)); self.dom_range.set_values(filters.get('dominance_min', 0), filters.get('dominance_max', 100)); self.sub_range.set_values(filters.get('submission_min', 0), filters.get('submission_max', 100)); selected_cups = filters.get('cup_sizes', [])
        
        # Load dick size, converting from inches (storage format) to the current UI format
        dick_min_in = filters.get('dick_size_min', 0)
        dick_max_in = filters.get('dick_size_max', 20)
        if self.unit_system == 'metric':
            self.dick_range.set_values(inches_to_cm(dick_min_in), inches_to_cm(dick_max_in))
        else:
            self.dick_range.set_values(dick_min_in, dick_max_in)

        if not selected_cups:
            min_idx, max_idx = 0, len(self.all_cup_sizes) - 1
        else:
            min_idx = self.cup_size_to_index.get(selected_cups[0], 0)
            max_idx = self.cup_size_to_index.get(selected_cups[-1], len(self.all_cup_sizes) - 1)
        self.cup_range.set_values(min_idx, max_idx)
        
        from PyQt6.QtWidgets import QListWidget # Import locally
        selected_nationalities = filters.get('nationalities', [])
        for i in range(self.nationality_list.count()): self.nationality_list.item(i).setSelected(self.nationality_list.item(i).text() in selected_nationalities)

        # --- Tree View Loading ---
        self.ethnicity_tree.set_checked_items(filters.get('ethnicities', []))
        self.location_tree.set_checked_items(filters.get('locations', []))

    def gather_current_filters(self) -> dict:
        """Reads all controls and returns the current filter dictionary."""
        filters = {}
        age_min, age_max = self.age_range.get_values(); perf_min, perf_max = self.perf_range.get_values(); act_min, act_max = self.act_range.get_values(); stam_min, stam_max = self.stam_range.get_values(); dom_min, dom_max = self.dom_range.get_values(); sub_min, sub_max = self.sub_range.get_values(); dick_min, dick_max = self.dick_range.get_values()
        cup_min_idx, cup_max_idx = self.cup_range.get_values()

        # Convert dick size from UI format back to inches (storage format)
        dick_val_min, dick_val_max = self.dick_range.get_values()
        if self.unit_system == 'metric':
            dick_size_min_in = cm_to_inches(dick_val_min)
            dick_size_max_in = cm_to_inches(dick_val_max)
        else:
            dick_size_min_in, dick_size_max_in = dick_val_min, dick_val_max
    
        # Only add cup size filter if it's not at the default max range
        if not (cup_min_idx == 0 and cup_max_idx == len(self.all_cup_sizes) - 1):
            filters['cup_sizes'] = self.all_cup_sizes[cup_min_idx : cup_max_idx + 1]
        filters.update({
            'go_to_list_only': self.go_to_only_checkbox.isChecked(), 'go_to_category_id': self.category_combo.currentData(), 'gender': 'Female' if self.gender_female_radio.isChecked() else 'Male' if self.gender_male_radio.isChecked() else 'Any', 'age_min': age_min, 'age_max': age_max, 'performance_min': perf_min, 'performance_max': perf_max, 'acting_min': act_min, 'acting_max': act_max, 'stamina_min': stam_min, 'stamina_max': stam_max, 'dominance_min': dom_min, 'dominance_max': dom_max, 'submission_min': sub_min, 'submission_max': sub_max, 'dick_size_min': dick_size_min_in, 'dick_size_max': dick_size_max_in, 'nationalities': [item.text() for item in self.nationality_list.selectedItems()],
            'ethnicities': self.ethnicity_tree.get_checked_items(),
            'locations': self.location_tree.get_checked_items(),

        })
        return filters
    
    def _filter_nationality_list(self, text: str):
        """Hides or shows items in the nationality list based on the filter text."""
        filter_text = text.lower()
        for i in range(self.nationality_list.count()):
            item = self.nationality_list.item(i)
            item_text = item.text().lower()
            # Set the item to be hidden if the filter text is not in its text
            item.setHidden(filter_text not in item_text)
    
    def _on_load_preset_clicked(self):
        preset_name = self.preset_combo.currentText()
        if not preset_name: return
        presets = self.settings_manager.get_talent_filter_presets(); preset_data = presets.get(preset_name)
        if preset_data: self.load_filters(preset_data)
        else: QMessageBox.warning(self, "Load Error", f"Could not find preset named '{preset_name}'.")
    def _on_save_preset_clicked(self):
        preset_name = self.preset_combo.currentText();
        if not preset_name: QMessageBox.warning(self, "Save Preset", "Please enter a name for the preset."); return
        current_filters = self.gather_current_filters(); presets = self.settings_manager.get_talent_filter_presets(); presets[preset_name] = current_filters; self.settings_manager.set_talent_filter_presets(presets); self._populate_presets_combobox(); self.preset_combo.setCurrentText(preset_name); QMessageBox.information(self, "Preset Saved", f"Preset '{preset_name}' has been saved.")
    def _on_delete_preset_clicked(self):
        preset_name = self.preset_combo.currentText();
        if not preset_name: return
        reply = QMessageBox.question(self, "Delete Preset", f"Are you sure you want to delete the preset '{preset_name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            presets = self.settings_manager.get_talent_filter_presets()
            if preset_name in presets: del presets[preset_name]; self.settings_manager.set_talent_filter_presets(presets); self._populate_presets_combobox()
    def set_category_combo_enabled(self, is_enabled: bool):
        self.category_combo.setEnabled(is_enabled)
        if not is_enabled: self.category_combo.setCurrentIndex(0)