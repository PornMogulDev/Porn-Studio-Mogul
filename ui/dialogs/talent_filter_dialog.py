from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QSpinBox, QLabel, QDoubleSpinBox,
    QListWidget, QPushButton, QDialogButtonBox, QWidget, QRadioButton, QButtonGroup,
    QFormLayout, QSizePolicy, QStyle, QComboBox
)
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin

class TalentFilterDialog(GeometryManagerMixin, QDialog):
    filters_applied = pyqtSignal(dict)

    def __init__(self, ethnicities: list, boob_cups: list, go_to_categories: list, current_filters: dict, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setWindowTitle("Advanced Talent Filter")
        self.setMinimumSize(300,500)
        self.current_filters = current_filters.copy()

        # Data for populating lists
        self.all_ethnicities = ethnicities
        self.all_boob_cups = boob_cups
        self.go_to_categories = go_to_categories

        self.setup_ui()
        self.load_current_filters()
        self._restore_geometry()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Go-To Category Filter ---
        category_group = QGroupBox("Go-To Category")
        category_layout = QVBoxLayout(category_group)
        self.category_combo = QComboBox()
        self.category_combo.addItem("Any", -1) # Use -1 as sentinel for 'no filter'
        for category in sorted(self.go_to_categories, key=lambda c: c['name']):
            self.category_combo.addItem(category['name'], category['id'])
        category_layout.addWidget(self.category_combo)
        main_layout.addWidget(category_group)

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
        age_layout = QHBoxLayout(age_group)
        self.min_age_spinbox = QSpinBox(); self.min_age_spinbox.setRange(18, 99)
        self.max_age_spinbox = QSpinBox(); self.max_age_spinbox.setRange(18, 99)
        age_layout.addWidget(QLabel("Min:")); age_layout.addWidget(self.min_age_spinbox)
        age_layout.addWidget(QLabel("Max:")); age_layout.addWidget(self.max_age_spinbox)
        main_layout.addWidget(age_group)

        # --- Core Skills ---
        skills_group = QGroupBox("Core Skills")
        skills_layout = QFormLayout(skills_group)
        self.min_perf_spin = QDoubleSpinBox(); self.min_perf_spin.setRange(0, 100)
        self.max_perf_spin = QDoubleSpinBox(); self.max_perf_spin.setRange(0, 100)
        self.min_act_spin = QDoubleSpinBox(); self.min_act_spin.setRange(0, 100)
        self.max_act_spin = QDoubleSpinBox(); self.max_act_spin.setRange(0, 100)
        self.min_stam_spin = QDoubleSpinBox(); self.min_stam_spin.setRange(0, 100)
        self.max_stam_spin = QDoubleSpinBox(); self.max_stam_spin.setRange(0, 100)
        skills_layout.addRow("Performance:", self._create_min_max_widget(self.min_perf_spin, self.max_perf_spin))
        skills_layout.addRow("Acting:", self._create_min_max_widget(self.min_act_spin, self.max_act_spin))
        skills_layout.addRow("Stamina:", self._create_min_max_widget(self.min_stam_spin, self.max_stam_spin))
        main_layout.addWidget(skills_group)

        # --- Attributes ---
        attr_group = QGroupBox("Attributes")
        attr_layout = QFormLayout(attr_group)
        self.min_ambition_spin = QSpinBox(); self.min_ambition_spin.setRange(1, 10)
        self.max_ambition_spin = QSpinBox(); self.max_ambition_spin.setRange(1, 10)
        attr_layout.addRow("Ambition:", self._create_min_max_widget(self.min_ambition_spin, self.max_ambition_spin))
        main_layout.addWidget(attr_group)
        
        # --- Physical Attributes ---
        phys_group = QGroupBox("Physical Attributes")
        phys_layout = QFormLayout(phys_group)
        self.min_dick_spin = QSpinBox(); self.min_dick_spin.setRange(0, 20)
        self.max_dick_spin = QSpinBox(); self.max_dick_spin.setRange(0, 20)
        phys_layout.addRow("Dick Size (in):", self._create_min_max_widget(self.min_dick_spin, self.max_dick_spin))
        
        self.cup_list = QListWidget()
        self.cup_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for cup in sorted(self.all_boob_cups): self.cup_list.addItem(cup)
        phys_layout.addRow("Cup Size:", self.cup_list)
        main_layout.addWidget(phys_group)

        # --- Ethnicity Filter ---
        ethnicity_group = QGroupBox("Ethnicity")
        ethnicity_layout = QVBoxLayout(ethnicity_group)
        self.ethnicity_list = QListWidget(); self.ethnicity_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for eth in sorted(self.all_ethnicities): self.ethnicity_list.addItem(eth)
        ethnicity_layout.addWidget(self.ethnicity_list)
        main_layout.addWidget(ethnicity_group)

        # --- Buttons ---
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        clear_btn = QPushButton("Clear Filters"); clear_btn.clicked.connect(self.clear_filters)
        button_layout.addWidget(clear_btn)
        revert_geometry_btn = QPushButton()
        revert_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogResetButton)
        revert_geometry_btn.setIcon(revert_icon)
        revert_geometry_btn.setToolTip("Revert window position and size to how it was when opened")
        revert_geometry_btn.clicked.connect(self.revert_to_initial_geometry)
        button_layout.addWidget(revert_geometry_btn)
        button_layout.addStretch()
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel)
        dialog_buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply_filters)
        dialog_buttons.rejected.connect(self.reject)
        button_layout.addWidget(dialog_buttons)
        main_layout.addWidget(button_container)

    def _create_min_max_widget(self, min_widget, max_widget):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(QLabel("Min:"))
        layout.addWidget(min_widget)
        layout.addWidget(QLabel("Max:"))
        layout.addWidget(max_widget)
        return container

    def load_current_filters(self):
        # Go-To Category
        category_id = self.current_filters.get('go_to_category_id', -1)
        index = self.category_combo.findData(category_id)
        if index != -1: self.category_combo.setCurrentIndex(index)
        # Gender
        gender = self.current_filters.get('gender', 'Any')
        if gender == "Female": self.gender_female_radio.setChecked(True)
        elif gender == "Male": self.gender_male_radio.setChecked(True)
        else: self.gender_any_radio.setChecked(True)
        # Age
        self.min_age_spinbox.setValue(self.current_filters.get('age_min', 18))
        self.max_age_spinbox.setValue(self.current_filters.get('age_max', 99))
        # Skills
        self.min_perf_spin.setValue(self.current_filters.get('performance_min', 0.0))
        self.max_perf_spin.setValue(self.current_filters.get('performance_max', 100.0))
        self.min_act_spin.setValue(self.current_filters.get('acting_min', 0.0))
        self.max_act_spin.setValue(self.current_filters.get('acting_max', 100.0))
        self.min_stam_spin.setValue(self.current_filters.get('stamina_min', 0.0))
        self.max_stam_spin.setValue(self.current_filters.get('stamina_max', 100.0))
        # Attributes
        self.min_ambition_spin.setValue(self.current_filters.get('ambition_min', 1))
        self.max_ambition_spin.setValue(self.current_filters.get('ambition_max', 10))
        # Physical
        self.min_dick_spin.setValue(self.current_filters.get('dick_size_min', 0))
        self.max_dick_spin.setValue(self.current_filters.get('dick_size_max', 20))
        selected_cups = self.current_filters.get('boob_cups', [])
        for i in range(self.cup_list.count()):
            item = self.cup_list.item(i)
            if item.text() in selected_cups: item.setSelected(True)
        # Ethnicity
        selected_ethnicities = self.current_filters.get('ethnicities', [])
        for i in range(self.ethnicity_list.count()):
            item = self.ethnicity_list.item(i)
            if item.text() in selected_ethnicities: item.setSelected(True)

    def apply_filters(self):
        filters = {
            'go_to_category_id': self.category_combo.currentData(),
            'gender': 'Female' if self.gender_female_radio.isChecked() else 'Male' if self.gender_male_radio.isChecked() else 'Any',
            'age_min': self.min_age_spinbox.value(), 'age_max': self.max_age_spinbox.value(),
            'performance_min': self.min_perf_spin.value(), 'performance_max': self.max_perf_spin.value(),
            'acting_min': self.min_act_spin.value(), 'acting_max': self.max_act_spin.value(),
            'stamina_min': self.min_stam_spin.value(), 'stamina_max': self.max_stam_spin.value(),
            'ambition_min': self.min_ambition_spin.value(), 'ambition_max': self.max_ambition_spin.value(),
            'dick_size_min': self.min_dick_spin.value(), 'dick_size_max': self.max_dick_spin.value(),
            'ethnicities': [item.text() for item in self.ethnicity_list.selectedItems()],
            'boob_cups': [item.text() for item in self.cup_list.selectedItems()]
        }
        self.filters_applied.emit(filters)
        self.accept()

    def clear_filters(self):
        self.category_combo.setCurrentIndex(0)
        self.gender_any_radio.setChecked(True)
        self.min_age_spinbox.setValue(18)
        self.max_age_spinbox.setValue(99)
        self.min_perf_spin.setValue(0.0)
        self.max_perf_spin.setValue(100.0)
        self.min_act_spin.setValue(0.0)
        self.max_act_spin.setValue(100.0)
        self.min_stam_spin.setValue(0.0)
        self.max_stam_spin.setValue(100.0)
        self.min_ambition_spin.setValue(1)
        self.max_ambition_spin.setValue(10)
        self.min_dick_spin.setValue(0)
        self.max_dick_spin.setValue(20)
        self.ethnicity_list.clearSelection()
        self.cup_list.clearSelection()