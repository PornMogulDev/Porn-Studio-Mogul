from typing import Dict, List, Optional
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLabel, QComboBox, QSpinBox, QLineEdit, 
                             QDialogButtonBox, QWidget, QScrollArea, QFrame, QCheckBox)
from PyQt6.QtCore import Qt, QSize

from ui.widgets.budget_slider_widget import BudgetSliderWidget
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin

class CallSheetDialog(GeometryManagerMixin, QDialog):
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setWindowTitle("Production Call Sheet")
        self.defaultSize = QSize(1000, 750)
        
        self.presenter = None
        
        # State holders for dynamically created widgets
        self.slider_widgets: Dict[str, BudgetSliderWidget] = {}
        self.policy_checkboxes: Dict[str, QCheckBox] = {}
        
        self.setup_ui()
        self._restore_geometry()

    def set_presenter(self, presenter):
        """Injected by UIManager"""
        self.presenter = presenter

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Top Section: 3 Columns ---
        columns_layout = QHBoxLayout()
        
        # Col 1: Logistics
        col_logistics = self._create_logistics_panel()
        columns_layout.addWidget(col_logistics, stretch=1)
        
        # Col 2: Crew (Jobs)
        col_crew = self._create_department_panel("Crew & Talent", "crew_container")
        columns_layout.addWidget(col_crew, stretch=2)
        
        # Col 3: Departments (Resources)
        col_resources = self._create_department_panel("Departments & Resources", "resource_container")
        columns_layout.addWidget(col_resources, stretch=2)
        
        main_layout.addLayout(columns_layout)

        # --- Middle Section: Policies ---
        # (Temporary placement as requested)
        policies_group = QGroupBox("On-Set Policies (Studio Defaults)")
        self.policies_layout = QHBoxLayout(policies_group) # Horizontal flow
        self.policies_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        main_layout.addWidget(policies_group)

        # --- Bottom Section: Budget Footer ---
        footer_frame = QFrame()
        footer_frame.setFrameShape(QFrame.Shape.StyledPanel)
        footer_layout = QHBoxLayout(footer_frame)
        
        lbl_budget = QLabel("Total Block Budget:")
        self.spin_total_budget = QSpinBox()
        self.spin_total_budget.setRange(500, 10_000_000)
        self.spin_total_budget.setPrefix("$")
        self.spin_total_budget.setSingleStep(500)
        self.spin_total_budget.valueChanged.connect(self.presenter.on_total_budget_changed)
        
        self.lbl_total_cost_preview = QLabel("Estimated Upfront Cost: $0")
        self.lbl_total_cost_preview.setStyleSheet("font-weight: bold; font-size: 14px;")

        footer_layout.addWidget(lbl_budget)
        footer_layout.addWidget(self.spin_total_budget)
        footer_layout.addStretch()
        footer_layout.addWidget(self.lbl_total_cost_preview)
        
        main_layout.addWidget(footer_frame)

        # --- Dialog Buttons ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.presenter.on_confirm)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def _create_logistics_panel(self) -> QGroupBox:
        group = QGroupBox("Logistics")
        layout = QVBoxLayout(group)
        
        # Name
        layout.addWidget(QLabel("Block Name:"))
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("e.g. Summer Shoot '98")
        layout.addWidget(self.edit_name)
        
        # Date
        date_layout = QHBoxLayout()
        self.spin_week = QSpinBox()
        self.spin_year = QSpinBox()
        self.spin_year.setRange(1990, 2100)
        self.spin_week.setRange(1, 52)
        date_layout.addWidget(QLabel("Week:"))
        date_layout.addWidget(self.spin_week)
        date_layout.addWidget(QLabel("Year:"))
        date_layout.addWidget(self.spin_year)
        layout.addLayout(date_layout)

        # Num Scenes
        layout.addWidget(QLabel("Scenes in Block:"))
        self.spin_num_scenes = QSpinBox()
        self.spin_num_scenes.setRange(1, 10)
        self.spin_num_scenes.valueChanged.connect(self.presenter.on_num_scenes_changed)
        layout.addWidget(self.spin_num_scenes)

        # Region (Placeholder/Fixed for now)
        layout.addWidget(QLabel("Region:"))
        self.combo_region = QComboBox()
        self.combo_region.addItem("South West (US)", "south_west_us")
        self.combo_region.setEnabled(False) # Fixed per design doc
        layout.addWidget(self.combo_region)
        
        # Location
        layout.addWidget(QLabel("Location:"))
        self.combo_location = QComboBox()
        self.combo_location.currentIndexChanged.connect(self.presenter.on_location_changed)
        layout.addWidget(self.combo_location)
        self.lbl_location_tags = QLabel("")
        self.lbl_location_tags.setWordWrap(True)
        self.lbl_location_tags.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.lbl_location_tags)
        
        # Visual Style
        layout.addWidget(QLabel("Visual Style:"))
        self.combo_style = QComboBox()
        self.combo_style.currentIndexChanged.connect(self.presenter.on_style_changed)
        layout.addWidget(self.combo_style)
        self.lbl_style_desc = QLabel("")
        self.lbl_style_desc.setWordWrap(True)
        self.lbl_style_desc.setStyleSheet("color: gray;")
        layout.addWidget(self.lbl_style_desc)
        
        layout.addStretch()
        return group

    def _create_department_panel(self, title: str, object_name: str) -> QGroupBox:
        group = QGroupBox(title)
        # Create a specific layout container that we can access later to add widgets
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        container = QWidget()
        container.setObjectName(object_name) # Used to find it later
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0,0,0,0)
        vbox.addStretch() # Push items to top
        
        scroll.setWidget(container)
        
        layout = QVBoxLayout(group)
        layout.addWidget(scroll)
        return group

    # --- Methods called by Presenter ---

    def populate_logistics_options(self, locations: List[Dict], styles: List[Dict]):
        # Populate Locations
        self.combo_location.blockSignals(True)
        self.combo_location.clear()
        for loc in locations:
            self.combo_location.addItem(loc['name'], loc['id'])
        self.combo_location.blockSignals(False)

        # Populate Styles
        self.combo_style.blockSignals(True)
        self.combo_style.clear()
        for style in styles:
            self.combo_style.addItem(style['name'], style['id'])
        self.combo_style.blockSignals(False)

    def populate_policies(self, policies: List[Dict], active_ids: List[str]):
        # Clear existing
        for i in reversed(range(self.policies_layout.count())): 
            self.policies_layout.itemAt(i).widget().setParent(None)
        self.policy_checkboxes.clear()

        for pol in policies:
            chk = QCheckBox(pol['name'])
            chk.setToolTip(pol['description'])
            chk.setChecked(pol['id'] in active_ids)
            chk.toggled.connect(lambda c, pid=pol['id']: self.presenter.on_policy_toggled(pid, c))
            self.policy_checkboxes[pol['id']] = chk
            self.policies_layout.addWidget(chk)

    def add_department_slider(self, dept_id: str, name: str, dept_type: str):
        """Creates a slider widget and places it in the correct column."""
        widget = BudgetSliderWidget(dept_id, name)
        widget.allocationChanged.connect(self.presenter.on_allocation_changed)
        widget.lockToggled.connect(self.presenter.on_lock_toggled)
        self.slider_widgets[dept_id] = widget

        # Find container based on type
        container_name = "crew_container" if dept_type == "crew" else "resource_container"
        container = self.findChild(QWidget, container_name)
        if container:
            layout = container.layout()
            # Insert before the stretch (which is the last item)
            layout.insertWidget(layout.count()-1, widget)

    def update_sliders(self, data: Dict[str, Dict], estimates: Dict[str, str]):
        """Batch update of all slider widgets."""
        for dept_id, info in data.items():
            if widget := self.slider_widgets.get(dept_id):
                estimate = estimates.get(dept_id, "")
                widget.update_state(
                    info['percent'], 
                    info['amount'], 
                    info['is_locked'], 
                    estimate
                )

    def update_logistics_info(self, style_desc: str, location_tags: List[str]):
        self.lbl_style_desc.setText(style_desc)
        self.lbl_location_tags.setText("Tags: " + ", ".join(location_tags))

    def set_budget_values(self, total_budget: int, estimated_cost: int):
        self.spin_total_budget.blockSignals(True)
        self.spin_total_budget.setValue(total_budget)
        self.spin_total_budget.blockSignals(False)
        self.lbl_total_cost_preview.setText(f"Upfront Cost: ${estimated_cost:,}")

    def set_schedule_values(self, week: int, year: int):
        self.spin_week.setValue(week)
        self.spin_year.setValue(year)
        
    def get_schedule_values(self):
        return self.spin_week.value(), self.spin_year.value()
    
    def get_name(self) -> str:
        return self.edit_name.text()
    
    def get_num_scenes(self) -> int:
        return self.spin_num_scenes.value()

    def commit_and_close(self):
        self.accept()