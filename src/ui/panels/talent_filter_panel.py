from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
QWidget, QVBoxLayout, QHBoxLayout, QLabel,
QPushButton, QRadioButton, QButtonGroup, QLineEdit,
QFormLayout, QComboBox, QCheckBox
)
from typing import List

from utils.formatters import inches_to_cm, cm_to_inches
from ui.widgets.talent_filter.categorical_range_filter_widget import CategoricalRangeFilterWidget
from ui.widgets.talent_filter.collapsible_group_box import CollapsibleGroupBox
from ui.widgets.talent_filter.checkable_hierarchy_tree_view import CheckableHierarchyTreeView

class TalentFilterPanel(QWidget):
    """Reusable panel for advanced talent filtering.

    This widget encapsulates the same filter controls as TalentFilterDialog
    but without dialog semantics (no Ok/Close buttons). It exposes its own
    Apply and Reset buttons and can optionally include scene/role selection
    controls for role-aware filtering contexts.

    The panel is intentionally dumb: it owns only UI state and emits
    signals describing user actions. A presenter or other coordinator is
    responsible for interpreting those actions and wiring them to the
    domain layer.
    """

    # Public API and internal signals
    filters_applied = pyqtSignal(dict)
    apply_requested = pyqtSignal()
    reset_requested = pyqtSignal()
    go_to_toggled = pyqtSignal(bool)

    # Signals for preset management
    load_preset_requested = pyqtSignal()
    save_preset_requested = pyqtSignal()
    delete_preset_requested = pyqtSignal()

    # Optional scene/role selection signals (only meaningful when
    # enable_scene_role is True).
    scene_changed = pyqtSignal(int)         # scene_id
    role_changed = pyqtSignal(int, int)     # scene_id, vp_id

    def __init__(
        self,
        ethnicities_hierarchy: dict,
        cup_sizes: list,
        nationalities: list,
        locations_by_region: dict,
        go_to_categories: list,
        settings_manager,
        enable_scene_role: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the filter panel.

        Parameters
        ----------
        ethnicities_hierarchy:
            Hierarchical ethnicity data used to populate the ethnicity tree.
        cup_sizes:
            Ordered list of cup size strings.
        nationalities:
            Flat list of nationality names.
        locations_by_region:
            Hierarchical location data for the location tree.
        go_to_categories:
            List of Go-To categories dictionaries with ``id`` and ``name``.
        settings_manager:
            Global settings manager used primarily for unit-system lookup.
        enable_scene_role:
            If True, include a simple scene/role selector row copied from the
            hiring dashboard's SceneRoleSelectorWidget (without its Apply
            button). When False, the panel only exposes generic talent
            filters and presets.
        """
        super().__init__(parent)

        self.settings_manager = settings_manager
        self.unit_system = self.settings_manager.get_setting("unit_system", "imperial")
        self.enable_scene_role = enable_scene_role

        # Data for populating controls
        self.ethnicities_hierarchy = ethnicities_hierarchy
        self.locations_by_region = locations_by_region
        self.all_nationalities = nationalities
        self.all_cup_sizes = cup_sizes
        self.cup_size_to_index = {cup: i for i, cup in enumerate(self.all_cup_sizes)}
        self.go_to_categories = go_to_categories

        # Optional scene/role state (only used when enable_scene_role is True)
        self.current_scene_id: int | None = None
        self.current_vp_id: int | None = None

        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Construct all child widgets and layout.

        This mirrors TalentFilterDialog.setup_ui, but without dialog
        button box and with optional scene/role selection at the top.
        """
        main_layout = QVBoxLayout(self)

        # Optional scene/role selector row (no Apply button)
        if self.enable_scene_role:
            scene_role_layout = QHBoxLayout()

            # Scene combo
            self.scene_combo = QComboBox()
            self.scene_combo.setPlaceholderText("Select a scene in casting...")
            scene_role_layout.addWidget(QLabel("Scene:"))
            scene_role_layout.addWidget(self.scene_combo)

            # Role combo
            self.role_combo = QComboBox()
            self.role_combo.setPlaceholderText("Select a role...")
            self.role_combo.setEnabled(False)
            scene_role_layout.addWidget(QLabel("Role:"))
            scene_role_layout.addWidget(self.role_combo)

            main_layout.addLayout(scene_role_layout)

        # --- Presets group -------------------------------------------------
        presets_group = CollapsibleGroupBox("Filter Presets")
        presets_layout = QHBoxLayout(presets_group)
        presets_layout.addWidget(QLabel("Preset:"))

        self.preset_combo = QComboBox()
        self.preset_combo.setEditable(True)
        self.preset_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.preset_combo.setToolTip(
            "Select a saved preset or type a new name to save."
        )
        presets_layout.addWidget(self.preset_combo)

        self.load_preset_button = QPushButton("Load")
        presets_layout.addWidget(self.load_preset_button)

        self.save_preset_button = QPushButton("Save")
        presets_layout.addWidget(self.save_preset_button)

        self.delete_preset_button = QPushButton("Delete")
        presets_layout.addWidget(self.delete_preset_button)

        main_layout.addWidget(presets_group)

        # --- Go-To list filter --------------------------------------------
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

        main_layout.addWidget(go_to_group)

        # --- Gender --------------------------------------------------------
        gender_group = CollapsibleGroupBox("Gender")
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

        # --- Age range -----------------------------------------------------
        from ui.widgets.talent_filter.range_filter_widget import RangeFilterWidget

        age_group = CollapsibleGroupBox("Age Range")
        age_layout = QVBoxLayout(age_group)

        self.age_range = RangeFilterWidget()
        self.age_range.set_range(18, 99)
        age_layout.addWidget(self.age_range)

        main_layout.addWidget(age_group)

        # --- Core skills ---------------------------------------------------
        skills_group = CollapsibleGroupBox("Core Skills")
        self.skills_layout = QFormLayout(skills_group)

        self.perf_range = RangeFilterWidget()
        self.perf_range.set_range(0, 100)

        self.act_range = RangeFilterWidget()
        self.act_range.set_range(0, 100)

        self.stam_range = RangeFilterWidget()
        self.stam_range.set_range(0, 100)

        self.dom_range = RangeFilterWidget()
        self.dom_range.set_range(0, 100)

        self.sub_range = RangeFilterWidget()
        self.sub_range.set_range(0, 100)

        self.skills_layout.addRow("Performance:", self.perf_range)
        self.skills_layout.addRow("Acting:", self.act_range)
        self.skills_layout.addRow("Stamina:", self.stam_range)
        self.skills_layout.addRow("Dominance:", self.dom_range)
        self.skills_layout.addRow("Submission:", self.sub_range)

        main_layout.addWidget(skills_group)

        # --- Physical attributes ------------------------------------------
        phys_group = CollapsibleGroupBox("Physical Attributes")
        self.phys_layout = QFormLayout(phys_group)

        self.dick_range = RangeFilterWidget()
        self.phys_layout.addRow("Dick Size", self.dick_range)
        self.update_dick_size_filter_ui()

        self.cup_range = CategoricalRangeFilterWidget(self.all_cup_sizes)
        self.phys_layout.addRow("Cup Size:", self.cup_range)

        main_layout.addWidget(phys_group)

        # --- Nationality ---------------------------------------------------
        from PyQt6.QtWidgets import QListWidget

        nationality_group = CollapsibleGroupBox("Nationality")
        nationality_layout = QVBoxLayout(nationality_group)

        self.nationality_filter_input = QLineEdit()
        self.nationality_filter_input.setPlaceholderText("Filter nationalities...")
        nationality_layout.addWidget(self.nationality_filter_input)

        self.nationality_list = QListWidget()
        self.nationality_list.setSelectionMode(
            QListWidget.SelectionMode.MultiSelection
        )
        self.nationality_list.addItems(sorted(self.all_nationalities))
        nationality_layout.addWidget(self.nationality_list)

        main_layout.addWidget(nationality_group)

        # --- Location tree -------------------------------------------------
        location_group = CollapsibleGroupBox("Location")
        location_layout = QVBoxLayout(location_group)

        self.location_tree = CheckableHierarchyTreeView()
        self.location_tree.populate_data(self.locations_by_region)
        location_layout.addWidget(self.location_tree)

        main_layout.addWidget(location_group)

        # --- Ethnicity tree ------------------------------------------------
        ethnicity_group = CollapsibleGroupBox("Ethnicity")
        ethnicity_layout = QVBoxLayout(ethnicity_group)

        self.ethnicity_tree = CheckableHierarchyTreeView()
        self.ethnicity_tree.populate_data(self.ethnicities_hierarchy)
        ethnicity_layout.addWidget(self.ethnicity_tree)

        main_layout.addWidget(ethnicity_group)

        # --- Layout stretch hints -----------------------------------------
        main_layout.setStretchFactor(nationality_group, 3)
        main_layout.setStretchFactor(location_group, 4)
        main_layout.setStretchFactor(ethnicity_group, 4)

        # --- Apply / Reset buttons ----------------------------------------
        button_row = QHBoxLayout()
        button_row.addStretch()
        self.apply_button = QPushButton("Apply")
        self.reset_button = QPushButton("Reset")
        button_row.addWidget(self.apply_button)
        button_row.addWidget(self.reset_button)
        main_layout.addLayout(button_row)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Wire child widget signals to panel-level signals."""
        # Go-To list toggle
        self.go_to_only_checkbox.stateChanged.connect(
            lambda state: self.go_to_toggled.emit(
                state == Qt.CheckState.Checked.value
            )
        )

        # Nationality filter typing
        self.nationality_filter_input.textChanged.connect(
            self._filter_nationality_list
        )

        # Preset management
        self.load_preset_button.clicked.connect(self.load_preset_requested)
        self.save_preset_button.clicked.connect(self.save_preset_requested)
        self.delete_preset_button.clicked.connect(self.delete_preset_requested)

        # Apply / Reset buttons
        self.apply_button.clicked.connect(self.apply_requested)
        self.reset_button.clicked.connect(self.reset_requested)

        # Optional scene/role signals
        if self.enable_scene_role:
            self.scene_combo.currentIndexChanged.connect(self._on_scene_changed)
            self.role_combo.currentIndexChanged.connect(self._on_role_changed)

    # ------------------------------------------------------------------
    # Scene/role helper methods (optional)
    # ------------------------------------------------------------------
    def populate_scenes(self, scenes: List[dict]) -> None:
        """Populate the scene dropdown without auto-selecting.

        When called with an empty list, the combo is disabled and shows a
        descriptive placeholder. This mirrors SceneRoleSelectorWidget but
        omits its Apply button.
        """
        if not self.enable_scene_role:
            return

        self.scene_combo.blockSignals(True)
        self.scene_combo.clear()
        self.current_scene_id = None
        self._clear_role_selection()

        if not scenes:
            self.scene_combo.setEnabled(False)
            self.scene_combo.setPlaceholderText("No scenes available for casting")
            self.scene_combo.setCurrentIndex(-1)
            self.scene_combo.blockSignals(False)
            return

        self.scene_combo.setEnabled(True)
        self.scene_combo.setPlaceholderText("Choose a scene in casting")

        for scene in scenes:
            self.scene_combo.addItem(scene['title'], scene['id'])

        self.scene_combo.setCurrentIndex(-1)
        self.scene_combo.blockSignals(False)

    def populate_roles(self, roles: List[dict]) -> None:
        """Populate the role dropdown without auto-selecting."""
        if not self.enable_scene_role:
            return

        self.role_combo.blockSignals(True)
        self.role_combo.clear()
        self.role_combo.setEnabled(False)
        self.current_vp_id = None

        if not roles:
            self.role_combo.setPlaceholderText("No uncast roles")
            self.role_combo.blockSignals(False)
            return

        for role in roles:
            self.role_combo.addItem(role['name'], role['id'])

        self.role_combo.setEnabled(True)
        self.role_combo.setCurrentIndex(-1)
        self.role_combo.blockSignals(False)

    def _on_scene_changed(self, index: int) -> None:
        if index < 0:
            self.current_scene_id = None
            self._clear_role_selection()
            return

        self.current_scene_id = self.scene_combo.currentData()
        if self.current_scene_id is not None:
            self.scene_changed.emit(self.current_scene_id)

    def _on_role_changed(self, index: int) -> None:
        if index < 0:
            self.current_vp_id = None
            return

        if self.current_scene_id is not None:
            self.current_vp_id = self.role_combo.currentData()
            if self.current_vp_id is not None:
                self.role_changed.emit(self.current_scene_id, self.current_vp_id)

    def _clear_role_selection(self) -> None:
        if not self.enable_scene_role:
            return
        self.role_combo.clear()
        self.role_combo.setEnabled(False)
        self.current_vp_id = None

    def get_current_scene_role_selection(self):
        """Return (scene_id, vp_id) if both are set, otherwise None."""
        if self.current_scene_id and self.current_vp_id:
            return (self.current_scene_id, self.current_vp_id)
        return None

    # ------------------------------------------------------------------
    # Public methods mirroring TalentFilterDialog's view API
    # ------------------------------------------------------------------
    def update_dick_size_filter_ui(self) -> None:
        """Set the label and range for the dick size filter.

        Values are always stored in inches; this method only affects
        the UI presentation (cm vs in) and the allowed range.
        """
        self.unit_system = self.settings_manager.get_setting("unit_system", "imperial")
        label = self.phys_layout.labelForField(self.dick_range)
        if self.unit_system == 'metric':
            if label:
                label.setText("Dick Size (cm):")
            self.dick_range.set_range(inches_to_cm(0), inches_to_cm(20))
        else:  # imperial
            if label:
                label.setText("Dick Size (in):")
            self.dick_range.set_range(0, 20)

    def populate_presets(self, presets: List[str], select_text: str | None = None) -> None:
        """Populate the presets combobox with a list of names."""
        current_text = select_text or self.preset_combo.currentText()
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        if presets:
            self.preset_combo.addItems(sorted(presets))

        index = self.preset_combo.findText(current_text)
        self.preset_combo.setCurrentIndex(index if index != -1 else -1)
        self.preset_combo.blockSignals(False)

    def load_filters(self, filters: dict) -> None:
        """Load a given filter dictionary into the UI controls."""
        # Standard controls
        self.go_to_only_checkbox.setChecked(filters.get('go_to_list_only', False))
        index = self.category_combo.findData(filters.get('go_to_category_id', -1))
        if index != -1:
            self.category_combo.setCurrentIndex(index)

        gender = filters.get('gender', 'Any')
        if gender == "Female":
            self.gender_female_radio.setChecked(True)
        elif gender == "Male":
            self.gender_male_radio.setChecked(True)
        else:
            self.gender_any_radio.setChecked(True)

        self.age_range.set_values(filters.get('age_min', 18), filters.get('age_max', 99))
        self.perf_range.set_values(filters.get('performance_min', 0), filters.get('performance_max', 100))
        self.act_range.set_values(filters.get('acting_min', 0), filters.get('acting_max', 100))
        self.stam_range.set_values(filters.get('stamina_min', 0), filters.get('stamina_max', 100))
        self.dom_range.set_values(filters.get('dominance_min', 0), filters.get('dominance_max', 100))
        self.sub_range.set_values(filters.get('submission_min', 0), filters.get('submission_max', 100))

        # Dick size: convert from inches (storage) to current UI units
        dick_min_in = filters.get('dick_size_min', 0)
        dick_max_in = filters.get('dick_size_max', 20)
        if self.unit_system == 'metric':
            self.dick_range.set_values(inches_to_cm(dick_min_in), inches_to_cm(dick_max_in))
        else:
            self.dick_range.set_values(dick_min_in, dick_max_in)

        selected_cups = filters.get('cup_sizes', [])
        if not selected_cups:
            min_idx, max_idx = 0, len(self.all_cup_sizes) - 1
        else:
            min_idx = self.cup_size_to_index.get(selected_cups[0], 0)
            max_idx = self.cup_size_to_index.get(selected_cups[-1], len(self.all_cup_sizes) - 1)
        self.cup_range.set_values(min_idx, max_idx)

        # Nationalities
        selected_nationalities = filters.get('nationalities', [])
        for i in range(self.nationality_list.count()):
            item = self.nationality_list.item(i)
            item.setSelected(item.text() in selected_nationalities)

        # Trees
        self.ethnicity_tree.set_checked_items(filters.get('ethnicities', []))
        self.location_tree.set_checked_items(filters.get('locations', []))

    def gather_current_filters(self) -> dict:
        """Read all controls and return the current filter dictionary."""
        filters: dict = {}

        age_min, age_max = self.age_range.get_values()
        perf_min, perf_max = self.perf_range.get_values()
        act_min, act_max = self.act_range.get_values()
        stam_min, stam_max = self.stam_range.get_values()
        dom_min, dom_max = self.dom_range.get_values()
        sub_min, sub_max = self.sub_range.get_values()

        # Convert dick size from UI format back to inches (storage format)
        dick_val_min, dick_val_max = self.dick_range.get_values()
        if self.unit_system == 'metric':
            dick_size_min_in = cm_to_inches(dick_val_min)
            dick_size_max_in = cm_to_inches(dick_val_max)
        else:
            dick_size_min_in, dick_size_max_in = dick_val_min, dick_val_max

        cup_min_idx, cup_max_idx = self.cup_range.get_values()
        if not (cup_min_idx == 0 and cup_max_idx == len(self.all_cup_sizes) - 1):
            filters['cup_sizes'] = self.all_cup_sizes[cup_min_idx: cup_max_idx + 1]

        filters.update({
            'go_to_list_only': self.go_to_only_checkbox.isChecked(),
            'go_to_category_id': self.category_combo.currentData(),
            'gender': (
                'Female' if self.gender_female_radio.isChecked()
                else 'Male' if self.gender_male_radio.isChecked()
                else 'Any'
            ),
            'age_min': age_min,
            'age_max': age_max,
            'performance_min': perf_min,
            'performance_max': perf_max,
            'acting_min': act_min,
            'acting_max': act_max,
            'stamina_min': stam_min,
            'stamina_max': stam_max,
            'dominance_min': dom_min,
            'dominance_max': dom_max,
            'submission_min': sub_min,
            'submission_max': sub_max,
            'dick_size_min': dick_size_min_in,
            'dick_size_max': dick_size_max_in,
            'nationalities': [
                item.text() for item in self.nationality_list.selectedItems()
            ],
            'ethnicities': self.ethnicity_tree.get_checked_items(),
            'locations': self.location_tree.get_checked_items(),
        })

        return filters

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _filter_nationality_list(self, text: str) -> None:
        """Hide/show items in the nationality list based on filter text."""
        filter_text = text.lower()
        for i in range(self.nationality_list.count()):
            item = self.nationality_list.item(i)
            item_text = item.text().lower()
            item.setHidden(filter_text not in item_text)

    def set_category_combo_enabled(self, is_enabled: bool) -> None:
        self.category_combo.setEnabled(is_enabled)
        if not is_enabled:
            self.category_combo.setCurrentIndex(0)