from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QCheckBox, QFormLayout
)

from utils.formatters import inches_to_cm, cm_to_inches
from ui.widgets.talent_filter.range_filter_widget import RangeFilterWidget
from ui.widgets.talent_filter.categorical_range_filter_widget import CategoricalRangeFilterWidget


class HiringTalentFilterWidget(QWidget):
    """
    Filter controls for the hiring dashboard.

    This widget mirrors the advanced talent filter dialog for the subset of
    filters that are relevant to role-based casting in the hiring dashboard.
    It intentionally omits gender and ethnicity controls because those are
    already enforced by the role/virtual performer selection.

    The widget is "dumb": it only owns UI state and emits filter dictionaries;
    all business rules about how those filters are interpreted live in the
    presenter.
    """

    # Emitted whenever any control changes; payload is the current filter dict.
    filters_changed = pyqtSignal(dict)

    def __init__(self, settings_manager, cup_sizes: list[str], parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.unit_system = self.settings_manager.get_setting("unit_system", "imperial")
        self.all_cup_sizes = cup_sizes
        self._cup_size_to_index = {cup: i for i, cup in enumerate(self.all_cup_sizes)}

        # Current role gender, used to enable/disable physical sliders so that
        # obviously conflicting combinations (e.g. dick size for female-only
        # roles) are not allowed.
        self._current_role_gender: str | None = None

        self._setup_ui()
        self._connect_signals()

        # Listen for live unit-system changes so the dick-size filter updates.
        if hasattr(self.settings_manager, "signals"):
            self.settings_manager.signals.setting_changed.connect(self._on_setting_changed)

    # ------------------------------------------------------------------
    # UI wiring
    # ------------------------------------------------------------------
    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Go-To filter ------------------------------------------------
        goto_layout = QHBoxLayout()
        self.goto_only_checkbox = QCheckBox("Only show Go-To talent")
        goto_layout.addWidget(self.goto_only_checkbox)
        goto_layout.addStretch()
        main_layout.addLayout(goto_layout)

        # --- Age range ---------------------------------------------------
        self.age_range = RangeFilterWidget()
        self.age_range.set_range(18, 99)
        self.age_range.set_values(18, 99)
        age_layout = QFormLayout()
        age_layout.addRow("Age Range:", self.age_range)
        main_layout.addLayout(age_layout)

        # --- Core skills -------------------------------------------------
        self.perf_range = RangeFilterWidget()
        self.perf_range.set_range(0, 100)
        self.perf_range.set_values(0, 100)

        self.act_range = RangeFilterWidget()
        self.act_range.set_range(0, 100)
        self.act_range.set_values(0, 100)

        self.stam_range = RangeFilterWidget()
        self.stam_range.set_range(0, 100)
        self.stam_range.set_values(0, 100)

        self.dom_range = RangeFilterWidget()
        self.dom_range.set_range(0, 100)
        self.dom_range.set_values(0, 100)

        self.sub_range = RangeFilterWidget()
        self.sub_range.set_range(0, 100)
        self.sub_range.set_values(0, 100)

        skills_layout = QFormLayout()
        skills_layout.addRow("Performance:", self.perf_range)
        skills_layout.addRow("Acting:", self.act_range)
        skills_layout.addRow("Stamina:", self.stam_range)
        skills_layout.addRow("Dominance:", self.dom_range)
        skills_layout.addRow("Submission:", self.sub_range)
        main_layout.addLayout(skills_layout)

        # --- Physical attributes ----------------------------------------
        self.phys_layout = QFormLayout()
        self.dick_range = RangeFilterWidget()
        self.phys_layout.addRow("Dick Size:", self.dick_range)
        self._update_dick_size_filter_ui()

        self.cup_range = CategoricalRangeFilterWidget(self.all_cup_sizes)
        # Default to full range
        if self.all_cup_sizes:
            self.cup_range.set_values(0, max(0, len(self.all_cup_sizes) - 1))
        self.phys_layout.addRow("Cup Size:", self.cup_range)
        main_layout.addLayout(self.phys_layout)

        main_layout.addStretch()

    def _connect_signals(self):
        # Go-to List widget
        self.goto_only_checkbox.stateChanged.connect(self._emit_filters_changed)

        # Range widgets
        self.age_range.valuesChanged.connect(lambda *_: self._emit_filters_changed())
        self.perf_range.valuesChanged.connect(lambda *_: self._emit_filters_changed())
        self.act_range.valuesChanged.connect(lambda *_: self._emit_filters_changed())
        self.stam_range.valuesChanged.connect(lambda *_: self._emit_filters_changed())
        self.dom_range.valuesChanged.connect(lambda *_: self._emit_filters_changed())
        self.sub_range.valuesChanged.connect(lambda *_: self._emit_filters_changed())
        self.dick_range.valuesChanged.connect(lambda *_: self._emit_filters_changed())
        self.cup_range.valuesChanged.connect(lambda *_: self._emit_filters_changed())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_role_gender(self, gender: str | None):
        """
        Update the role gender and toggle physical sliders accordingly.

        The hiring dashboard already enforces gender eligibility at the
        database/query layer using the virtual performer. This method is only
        concerned with ensuring that UI-level physical filters do not allow
        obviously conflicting combinations:

        - For strictly male roles, the dick-size range is available and the
          cup-size range is disabled and ignored.
        - For strictly female roles, the cup-size range is available and the
          dick-size range is disabled and ignored.
        - For "Any" or unknown genders, both physical sliders remain enabled.
        """
        self._current_role_gender = gender
        gender_normalized = (gender or "Any").strip().lower()

        if gender_normalized == "male":
            # Dick size is meaningful; cup size is not.
            self.dick_range.setEnabled(True)
            self.cup_range.setEnabled(False)
        elif gender_normalized == "female":
            # Cup size is meaningful; dick size is not.
            self.dick_range.setEnabled(False)
            self.cup_range.setEnabled(True)
        else:
            # Fallback: allow both.
            self.dick_range.setEnabled(True)
            self.cup_range.setEnabled(True)

        # Emit updated filters so the presenter can re-apply them.
        self._emit_filters_changed()

    def get_current_filters(self) -> dict:
        """
        Return the current filter state as a plain dictionary.

        Numeric dick-size filters are always returned in inches to match the
        storage format used by the database. When the global unit system is
        metric, values are converted back from centimeters.
        """
        filters: dict = {}

        # Go-To List
        filters["go_to_list_only"] = self.goto_only_checkbox.isChecked()

        # Age
        age_min, age_max = self.age_range.get_values()
        filters["age_min"] = age_min
        filters["age_max"] = age_max

        # Core skills
        perf_min, perf_max = self.perf_range.get_values()
        act_min, act_max = self.act_range.get_values()
        stam_min, stam_max = self.stam_range.get_values()
        dom_min, dom_max = self.dom_range.get_values()
        sub_min, sub_max = self.sub_range.get_values()

        filters.update({
            "performance_min": perf_min,
            "performance_max": perf_max,
            "acting_min": act_min,
            "acting_max": act_max,
            "stamina_min": stam_min,
            "stamina_max": stam_max,
            "dominance_min": dom_min,
            "dominance_max": dom_max,
            "submission_min": sub_min,
            "submission_max": sub_max,
        })

        # Physical: dick size (inches in storage)
        gender_normalized = (self._current_role_gender or "Any").strip().lower()
        if self.dick_range.isEnabled() and gender_normalized != "female":
            dick_min_ui, dick_max_ui = self.dick_range.get_values()
            if self.unit_system == "metric":
                dick_min_in = cm_to_inches(dick_min_ui)
                dick_max_in = cm_to_inches(dick_max_ui)
            else:
                dick_min_in, dick_max_in = dick_min_ui, dick_max_ui
            filters["dick_size_min"] = dick_min_in
            filters["dick_size_max"] = dick_max_in

        # Physical: cup sizes (list of strings). Only add if restricted and enabled.
        if self.cup_range.isEnabled() and gender_normalized != "male" and self.all_cup_sizes:
            cup_min_idx, cup_max_idx = self.cup_range.get_values()
            if not (cup_min_idx == 0 and cup_max_idx == len(self.all_cup_sizes) - 1):
                filters["cup_sizes"] = self.all_cup_sizes[cup_min_idx: cup_max_idx + 1]

        return filters

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _emit_filters_changed(self):
        """Gather current filters and emit the filters_changed signal."""
        self.filters_changed.emit(self.get_current_filters())

    def _update_dick_size_filter_ui(self):
        """Update dick-size label and range based on the current unit system."""
        label = self.phys_layout.labelForField(self.dick_range)
        if self.unit_system == "metric":
            if label:
                label.setText("Dick Size (cm):")
            self.dick_range.set_range(inches_to_cm(0), inches_to_cm(20))
            self.dick_range.set_values(inches_to_cm(0), inches_to_cm(20))
        else:
            if label:
                label.setText("Dick Size (in):")
            self.dick_range.set_range(0, 20)
            self.dick_range.set_values(0, 20)

    def _on_setting_changed(self, key: str):
        """React to global unit-system changes while the widget is visible."""
        if key != "unit_system":
            return

        # Capture current logical inch values, then rebuild the UI range and
        # re-apply those values in the new unit system.
        current_filters = self.get_current_filters()
        self.unit_system = self.settings_manager.get_setting("unit_system", "imperial")
        self._update_dick_size_filter_ui()

        dick_min_in = current_filters.get("dick_size_min", 0)
        dick_max_in = current_filters.get("dick_size_max", 20)
        if self.unit_system == "metric":
            self.dick_range.set_values(inches_to_cm(dick_min_in), inches_to_cm(dick_max_in))
        else:
            self.dick_range.set_values(dick_min_in, dick_max_in)

        # Emit an updated filter set so the presenter can re-apply.
        self._emit_filters_changed()