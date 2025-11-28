from typing import Dict, List
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
        
        self.slider_widgets: Dict[str, BudgetSliderWidget] = {}
        
        # Explicit references for layouts to ensure sliders are added correctly
        self.crew_layout = None 
        self.resource_layout = None
        
        # Date constraints
        self.min_year = 2000
        self.min_week = 1

        self.setup_ui()
        self._restore_geometry()

    def set_presenter(self, presenter):
        """Injected by UIManager"""
        self.presenter = presenter
        self._connect_static_signals()

    def _connect_static_signals(self):
        """Connects signals for widgets created in setup_ui that depend on the presenter."""
        if not self.presenter: return
        
        self.spin_budget_per_scene.valueChanged.connect(self.presenter.on_budget_per_scene_changed)
        self.button_box.accepted.connect(self.presenter.on_confirm)
        self.spin_num_scenes.valueChanged.connect(self.presenter.on_num_scenes_changed)
        self.combo_location.currentIndexChanged.connect(self.presenter.on_location_changed)
        self.combo_style.currentIndexChanged.connect(self.presenter.on_style_changed)
        self.spin_year.valueChanged.connect(self._update_date_constraints)

        self.combo_picture_set.currentIndexChanged.connect(self.presenter.on_picture_set_changed)
        self.spin_camera_count.valueChanged.connect(self._on_camera_count_changed)
        
        for combo in self.camera_mount_combos:
            combo.currentIndexChanged.connect(self.presenter.on_camera_config_changed)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Top Section: 3 Columns ---
        columns_layout = QHBoxLayout()
        
        # Col 1: Logistics & Budget
        col_logistics = self._create_logistics_panel()
        columns_layout.addWidget(col_logistics, stretch=1)
        
        # Col 2: Crew (Jobs)
        col_crew, self.crew_layout = self._create_department_panel("Crew")
        columns_layout.addWidget(col_crew, stretch=2)
        
        # Col 3: Departments (Resources) & Cost Preview
        col_resources, self.resource_layout = self._create_department_panel("Departments")
        
        # Add the Cost Preview to the bottom of the Resources column (outside scroll area)
        self.lbl_total_cost_preview = QLabel("Estimated Upfront Cost: $0")
        self.lbl_total_cost_preview.setObjectName("CallSheetTotalCost")
        self.lbl_total_cost_preview.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        # Access the layout of the GroupBox to add the footer
        col_resources.layout().addWidget(self.lbl_total_cost_preview)
        
        columns_layout.addWidget(col_resources, stretch=2)
        
        main_layout.addLayout(columns_layout)

        # --- Bottom Buttons ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def _create_logistics_panel(self) -> QGroupBox:
        group = QGroupBox("Logistics & Budget")
        layout = QVBoxLayout(group)
        
        # Name
        layout.addWidget(QLabel("Block Name:"))
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("e.g. Summer Shoot '98")
        layout.addWidget(self.edit_name)
        
        # Budget
        layout.addWidget(QLabel("Budget per Scene:"))
        self.spin_budget_per_scene = QSpinBox()
        self.spin_budget_per_scene.setRange(0, 10000000)
        self.spin_budget_per_scene.setPrefix("$")
        self.spin_budget_per_scene.setSingleStep(500)
        layout.addWidget(self.spin_budget_per_scene)

        # Date
        date_layout = QHBoxLayout()
        self.spin_week = QSpinBox()
        self.spin_year = QSpinBox()
        # Constraints set by set_date_limits
        date_layout.addWidget(QLabel("Week:"))
        date_layout.addWidget(self.spin_week)
        date_layout.addWidget(QLabel("Year:"))
        date_layout.addWidget(self.spin_year)
        layout.addLayout(date_layout)

        # Num Scenes
        layout.addWidget(QLabel("Scenes in Block:"))
        self.spin_num_scenes = QSpinBox()
        self.spin_num_scenes.setRange(1, 4)
        layout.addWidget(self.spin_num_scenes)

        # Region (Placeholder/Fixed)
        layout.addWidget(QLabel("Region:"))
        self.combo_region = QComboBox()
        self.combo_region.addItem("South West (US)", "south_west_us")
        self.combo_region.setEnabled(False) 
        layout.addWidget(self.combo_region)
        
        # Location
        layout.addWidget(QLabel("Location:"))
        self.combo_location = QComboBox()
        layout.addWidget(self.combo_location)
        self.lbl_location_tags = QLabel("")
        self.lbl_location_tags.setObjectName("CallSheetMetaLabel")
        self.lbl_location_tags.setWordWrap(True)
        layout.addWidget(self.lbl_location_tags)
        
        # Visual Style
        layout.addWidget(QLabel("Visual Style:"))
        self.combo_style = QComboBox()
        layout.addWidget(self.combo_style)
        self.lbl_style_desc = QLabel("")
        self.lbl_style_desc.setObjectName("CallSheetMetaLabel")
        self.lbl_style_desc.setWordWrap(True)
        layout.addWidget(self.lbl_style_desc)

        # Picture Set Type
        layout.addWidget(QLabel("Picture Set:"))
        self.combo_picture_set = QComboBox()
        layout.addWidget(self.combo_picture_set)

        # Camera Configuration
        layout.addWidget(QLabel("Cameras:"))
        self.spin_camera_count = QSpinBox()
        self.spin_camera_count.setRange(1, 3)
        layout.addWidget(self.spin_camera_count)

        self.camera_mount_combos = []
        self.camera_widgets_container = QWidget()
        cam_layout = QVBoxLayout(self.camera_widgets_container)
        cam_layout.setContentsMargins(0, 0, 0, 0)
        
        mount_options = ["Handheld / Operator", "Tripod / Static"]
        
        for i in range(3):
            lbl = QLabel(f"Cam {i+1} Mount:")
            combo = QComboBox()
            combo.addItems(mount_options)
            cam_layout.addWidget(lbl)
            cam_layout.addWidget(combo)
            self.camera_mount_combos.append(combo)
            # Store label ref to hide it later if needed
            combo.setProperty("label_widget", lbl) 
            
        layout.addWidget(self.camera_widgets_container)
        # Initialize visibility based on default count (1)
        self._on_camera_count_changed(self.spin_camera_count.value())
        
        layout.addStretch()
        return group

    def _create_department_panel(self, title: str):
        """Returns (GroupBox, Layout_For_Sliders)"""
        group = QGroupBox(title)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0,0,0,0)
        vbox.addStretch() # Push items to top
        
        scroll.setWidget(container)
        
        main_layout = QVBoxLayout(group)
        main_layout.addWidget(scroll)
        
        return group, vbox

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

    def add_department_slider(self, dept_id: str, name: str, dept_type: str, show_assignment: bool = False):
        """Creates a slider widget and places it in the correct column."""
        widget = BudgetSliderWidget(dept_id, name, show_assignment=show_assignment)
        if self.presenter:
            widget.allocationChanged.connect(self.presenter.on_allocation_changed)
            widget.lockToggled.connect(self.presenter.on_lock_toggled)
        self.slider_widgets[dept_id] = widget

        # Explicit check for location or resource types
        is_crew = str(dept_type).lower() == "crew"
        target_layout = self.crew_layout if is_crew else self.resource_layout
        
        if target_layout:
            # Insert before the stretch (which is the last item)
            target_layout.insertWidget(target_layout.count()-1, widget)
            
    def set_date_limits(self, current_year: int, current_week: int):
        """Configures the spinners so users can't pick past dates."""
        self.min_year = current_year
        self.min_week = current_week
        
        # Block signals to prevent redundant logic triggers during setup
        self.spin_year.blockSignals(True)
        self.spin_week.blockSignals(True)
        
        self.spin_year.setRange(current_year, current_year + 10)
        
        # Initial check for current year constraints
        self._update_date_constraints()
        
        self.spin_year.blockSignals(False)
        self.spin_week.blockSignals(False)

    def populate_picture_set_options(self, options: List[Dict]):
        self.combo_picture_set.blockSignals(True)
        self.combo_picture_set.clear()
        for opt in options:
            self.combo_picture_set.addItem(opt['name'], opt['id'])
        self.combo_picture_set.blockSignals(False)

    def _on_camera_count_changed(self, count):
        """Updates visibility of mount combos based on count."""
        for i, combo in enumerate(self.camera_mount_combos):
            visible = i < count
            combo.setVisible(visible)
            if lbl := combo.property("label_widget"):
                lbl.setVisible(visible)
        
        if self.presenter:
            self.presenter.on_camera_config_changed()

    def get_camera_config(self):
        count = self.spin_camera_count.value()
        # Return list of mount strings ("Handheld / Operator" or "Tripod / Static")
        mounts = [c.currentText().split(" ")[0] for c in self.camera_mount_combos]
        return count, mounts

    def _update_date_constraints(self):
        """Adjusts week min based on selected year."""
        selected_year = self.spin_year.value()
        
        if selected_year == self.min_year:
            # Can't schedule before today in the current year
            self.spin_week.setRange(self.min_week, 52)
        else:
            # Future years allow any week
            self.spin_week.setRange(1, 52)

    def update_sliders(self, data: Dict[str, Dict], estimates: Dict[str, str]):
        """Batch update of all slider widgets."""
        for dept_id, info in data.items():
            if widget := self.slider_widgets.get(dept_id):
                estimate = estimates.get(dept_id, "")
                
                widget.update_state(
                    percent=info['percent'], 
                    amount=info['amount'], 
                    is_user_locked=info['is_user_locked'], 
                    is_system_disabled=info['is_system_disabled'],
                    estimate_text=estimate
                )

    def update_logistics_info(self, style_desc: str, location_tags: List[str]):
        self.lbl_style_desc.setText(style_desc)
        tag_text = ", ".join(location_tags) if location_tags else "None"
        self.lbl_location_tags.setText(f"Tags: {tag_text}")

    def set_budget_values(self, budget_per_scene: int, estimated_cost: int):
        self.spin_budget_per_scene.blockSignals(True)
        self.spin_budget_per_scene.setValue(budget_per_scene)
        self.spin_budget_per_scene.blockSignals(False)
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