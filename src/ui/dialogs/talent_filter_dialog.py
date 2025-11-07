from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QListWidget, QWidget, QRadioButton, QButtonGroup,
    QFormLayout, QComboBox, QCheckBox, QDialogButtonBox
)
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin
from ui.presenters.talent_filter_presenter import TalentFilterPresenter
from ui.widgets.range_filter_widget import RangeFilterWidget

class TalentFilterDialog(GeometryManagerMixin, QDialog):
    # --- Public API for the owner (TalentTabPresenter) ---
    filters_applied = pyqtSignal(dict)

    # --- Internal Signals for the Presenter ---
    apply_requested = pyqtSignal()
    reset_requested = pyqtSignal()
    apply_and_close_requested = pyqtSignal()
    go_to_toggled = pyqtSignal(bool)

    def __init__(self, ethnicities: list, boob_cups: list, go_to_categories: list, current_filters: dict, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setWindowTitle("Advanced Talent Filter")
        self.defaultSize = QSize(650, 850) # Increased height for new sliders

        self.all_ethnicities = ethnicities
        self.all_boob_cups = boob_cups
        self.go_to_categories = go_to_categories

        self.setup_ui()
        self.connect_signals()

        # --- Presenter Creation ---
        # The view creates its own presenter and its lifecycle is tied to the dialog's.
        self.presenter = TalentFilterPresenter(self, current_filters)
        self.presenter.load_initial_data() # Command the presenter to populate the view

        self._restore_geometry()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Go-To Category Filter ---
        go_to_group = QGroupBox("Go-To List Filter")
        go_to_layout = QVBoxLayout(go_to_group)
        self.go_to_only_checkbox = QCheckBox("Show only talent in Go-To Lists")
        go_to_layout.addWidget(self.go_to_only_checkbox)

        self.category_combo = QComboBox()
        self.category_combo.setEnabled(False)
        self.category_combo.addItem("Any", -1)
        for category in sorted(self.go_to_categories, key=lambda c: c['name']):
            self.category_combo.addItem(category['name'], category['id'])
        go_to_layout.addWidget(self.category_combo)
        main_layout.addWidget(go_to_group)

        # --- Gender Filter ---
        gender_group = QGroupBox("Gender")
        gender_layout = QHBoxLayout(gender_group)
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
        main_layout.addWidget(gender_group)

        # --- Age Filter ---
        age_group = QGroupBox("Age Range")
        age_layout = QVBoxLayout(age_group)
        self.age_range = RangeFilterWidget()
        self.age_range.set_range(18, 99)
        age_layout.addWidget(self.age_range)
        main_layout.addWidget(age_group)

        # --- Core Skills ---
        skills_group = QGroupBox("Core Skills")
        skills_layout = QFormLayout(skills_group)
        self.perf_range = RangeFilterWidget(); self.perf_range.set_range(0, 100)
        self.act_range = RangeFilterWidget(); self.act_range.set_range(0, 100)
        self.stam_range = RangeFilterWidget(); self.stam_range.set_range(0, 100)
        self.dom_range = RangeFilterWidget(); self.dom_range.set_range(0, 100)
        self.sub_range = RangeFilterWidget(); self.sub_range.set_range(0, 100)
        skills_layout.addRow("Performance:", self.perf_range)
        skills_layout.addRow("Acting:", self.act_range)
        skills_layout.addRow("Stamina:", self.stam_range)
        skills_layout.addRow("Dominance:", self.dom_range)
        skills_layout.addRow("Submission:", self.sub_range)
        main_layout.addWidget(skills_group)
        
        # --- Physical Attributes ---
        phys_group = QGroupBox("Physical Attributes")
        phys_layout = QFormLayout(phys_group)
        self.dick_range = RangeFilterWidget()
        self.dick_range.set_range(0, 20)
        phys_layout.addRow("Dick Size (in):", self.dick_range)
        
        self.cup_list = QListWidget()
        self.cup_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for cup in self.all_boob_cups: self.cup_list.addItem(cup)
        cup_label = QLabel("Cup Size:")
        cup_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        phys_layout.addRow(cup_label, self.cup_list)
        main_layout.addWidget(phys_group)

        # --- Ethnicity Filter ---
        ethnicity_group = QGroupBox("Ethnicity")
        ethnicity_layout = QVBoxLayout(ethnicity_group)
        self.ethnicity_list = QListWidget(); self.ethnicity_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        # Sort "Any" to the top
        for eth in sorted(self.all_ethnicities, key=lambda x: (x != "Any", x)): self.ethnicity_list.addItem(eth)
        ethnicity_layout.addWidget(self.ethnicity_list)
        main_layout.addWidget(ethnicity_group)

        # --- Dialog Buttons ---
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Apply |
            QDialogButtonBox.StandardButton.Reset |
            QDialogButtonBox.StandardButton.Close
        )
        button_box.button(QDialogButtonBox.StandardButton.Ok).clicked.connect(self.apply_and_close_requested)
        button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply_requested)
        button_box.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(self.reset_requested)
        button_box.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.reject)
        main_layout.addWidget(button_box)

    def connect_signals(self):
        self.go_to_only_checkbox.stateChanged.connect(
            lambda state: self.go_to_toggled.emit(state == Qt.CheckState.Checked.value)
        )

    def set_category_combo_enabled(self, is_enabled: bool):
        """Public method for the presenter to command UI state changes."""
        self.category_combo.setEnabled(is_enabled)
        if not is_enabled:
            self.category_combo.setCurrentIndex(0) # Reset to 'Any'

    def load_filters(self, filters: dict):
        """Loads a given filter dictionary into the UI controls."""
        # Go-To Category
        self.go_to_only_checkbox.setChecked(filters.get('go_to_list_only', False))
        index = self.category_combo.findData(filters.get('go_to_category_id', -1))
        if index != -1: self.category_combo.setCurrentIndex(index)

        # Gender
        gender = filters.get('gender', 'Any')
        if gender == "Female": self.gender_female_radio.setChecked(True)
        elif gender == "Male": self.gender_male_radio.setChecked(True)
        else: self.gender_any_radio.setChecked(True)

        # Range Widgets
        self.age_range.set_values(filters.get('age_min', 18), filters.get('age_max', 99))
        self.perf_range.set_values(filters.get('performance_min', 0), filters.get('performance_max', 100))
        self.act_range.set_values(filters.get('acting_min', 0), filters.get('acting_max', 100))
        self.stam_range.set_values(filters.get('stamina_min', 0), filters.get('stamina_max', 100))
        self.dom_range.set_values(filters.get('dominance_min', 0), filters.get('dominance_max', 100))
        self.sub_range.set_values(filters.get('submission_min', 0), filters.get('submission_max', 100))
        self.dick_range.set_values(filters.get('dick_size_min', 0), filters.get('dick_size_max', 20))
        
        # Lists
        selected_cups = filters.get('boob_cups', [])
        for i in range(self.cup_list.count()):
            item = self.cup_list.item(i)
            item.setSelected(item.text() in selected_cups)

        selected_ethnicities = filters.get('ethnicities', [])
        for i in range(self.ethnicity_list.count()):
            item = self.ethnicity_list.item(i)
            item.setSelected(item.text() in selected_ethnicities)

    def gather_current_filters(self) -> dict:
        """Reads all controls and returns the current filter dictionary."""
        age_min, age_max = self.age_range.get_values()
        perf_min, perf_max = self.perf_range.get_values()
        act_min, act_max = self.act_range.get_values()
        stam_min, stam_max = self.stam_range.get_values()
        dom_min, dom_max = self.dom_range.get_values()
        sub_min, sub_max = self.sub_range.get_values()
        dick_min, dick_max = self.dick_range.get_values()

        return {
            'go_to_list_only': self.go_to_only_checkbox.isChecked(),
            'go_to_category_id': self.category_combo.currentData(),
            'gender': 'Female' if self.gender_female_radio.isChecked() else 'Male' if self.gender_male_radio.isChecked() else 'Any',
            'age_min': age_min, 'age_max': age_max,
            'performance_min': perf_min, 'performance_max': perf_max,
            'acting_min': act_min, 'acting_max': act_max,
            'stamina_min': stam_min, 'stamina_max': stam_max,
            'dominance_min': dom_min, 'dominance_max': dom_max,
            'submission_min': sub_min, 'submission_max': sub_max,
            'dick_size_min': dick_min, 'dick_size_max': dick_max,
            'ethnicities': [item.text() for item in self.ethnicity_list.selectedItems()],
            'boob_cups': [item.text() for item in self.cup_list.selectedItems()]
        }