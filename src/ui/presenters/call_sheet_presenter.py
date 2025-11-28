from typing import TYPE_CHECKING
from PyQt6.QtCore import QObject

from services.builders.call_sheet_builder import ShootingBlocBuilder
from utils import time_utils

if TYPE_CHECKING:
    from ui.dialogs.call_sheet_dialog import CallSheetDialog
    from core.game_controller import GameController

class CallSheetPresenter(QObject):
    def __init__(self, controller: 'GameController', view: 'CallSheetDialog', parent=None):
        super().__init__(parent)
        self.controller = controller
        self.view = view
        
        self.builder = self.controller.get_shooting_bloc_builder()
        
        # Cache both dictionaries
        self.departments_cache = self.controller.data_manager.production_departments
        self.jobs_cache = self.controller.data_manager.production_jobs # Add this
        self.styles_cache = self.controller.data_manager.visual_styles
        self.locations_cache = self.controller.data_manager.production_locations
        self.picture_sets_cache = self.controller.data_manager.picture_set_types

    def initialize(self):
        """Called by View after UI setup."""
        # 1. Setup default Logistics
        locations = list(self.locations_cache.values())
        styles = list(self.styles_cache.values())
        pst_options = list(self.picture_sets_cache.values())
        self.view.populate_logistics_options(locations, styles)
        self.view.populate_picture_set_options(pst_options)

        # Force update of tags/descriptions for the default selections (Index 0)
        if locations:
             # Ensure builder has the ID of the first item
            self.on_location_changed(0)
        if styles:
            self.on_style_changed(0)
        
        # 2. Setup Defaults in Builder and Date Constraints
        current_week = self.controller.game_state.absolute_week
        year, week = time_utils.from_absolute(current_week)
        
        self.view.set_date_limits(year, week)
        self.view.set_schedule_values(week, year)
        self.view.spin_num_scenes.setValue(2)

        # 3. Create Sliders dynamically
        
        # A. Add Crew Sliders (From Production Jobs)
        for job_id, job_def in self.jobs_cache.items():
            self.view.add_department_slider(
                job_id,
                job_def.get('name', job_id.title()),
                'crew', # Hardcode type string for column logic
                show_assignment=True
            )

        # B. Add Location Slider (Dynamic)
        # This is a special resource managed by the builder, not in the static DB cache
        self.view.add_department_slider(
            'location_logistics',
            'Location & Set',
            'resource'
        )

        # C. Add Resource Sliders (From Production Departments)
        for dept_id, dept_def in self.departments_cache.items():
            self.view.add_department_slider(
                dept_id, 
                dept_def.get('name', dept_id.title()), 
                'resource' # Hardcode type string
            )

        # 4. Initial Refresh
        self._sync_view_from_builder()

    def _sync_view_from_builder(self):
        """Updates all UI elements to match Builder state."""
        data = self.builder.get_ui_data()
        
        # 1. Sliders
        self.view.update_sliders(data['allocations'], data['estimates'])
        
        # 2. Cost & Budget Display
        self.view.set_budget_values(data['budget_per_scene'], data['total_cost'])
        
        # 3. Logistics Text
        style = self.styles_cache.get(self.builder.visual_style_id, {})
        loc = self.locations_cache.get(self.builder.location_id, {})
        self.view.update_logistics_info(
            style.get('description', ''),
            loc.get('tags', [])
        )

    # --- Events ---

    def on_allocation_changed(self, dept_id: str, value: float):
        self.builder.update_allocation(dept_id, value)
        self._sync_view_from_builder()

    def on_lock_toggled(self, dept_id: str, is_locked: bool):
        self.builder.toggle_user_lock(dept_id, is_locked)
        self._sync_view_from_builder()

    def on_budget_per_scene_changed(self, value: int):
        self.builder.set_budget_per_scene(value)
        self._sync_view_from_builder()

    def on_location_changed(self, index: int):
        loc_id = self.view.combo_location.currentData()
        if loc_id:
            self.builder.set_location(loc_id)
            self._sync_view_from_builder()

    def on_style_changed(self, index: int):
        style_id = self.view.combo_style.currentData()
        if style_id:
            self.builder.visual_style_id = style_id
            self._sync_view_from_builder()

    def on_picture_set_changed(self, index: int):
        pst_id = self.view.combo_picture_set.currentData()
        if pst_id:
            self.builder.set_picture_set_type(pst_id)
            self._sync_view_from_builder()

    def on_camera_config_changed(self):
        # Triggered by count spinbox or any mount combo
        count, mounts = self.view.get_camera_config()
        self.builder.set_camera_config(count, mounts)
        self._sync_view_from_builder()
        
    def on_num_scenes_changed(self, value: int):
        # Only affects cost calculation
        self.builder.set_num_scenes(value)
        self._sync_view_from_builder()

    def on_confirm(self):
        week, year = self.view.get_schedule_values()
        abs_week = time_utils.to_absolute(year, week)
        num_scenes = self.view.get_num_scenes()
        name = self.view.get_name()
        
        # Generate Payload
        # Ensure builder has latest scene count (commit uses internal state)
        self.builder.set_num_scenes(num_scenes)
        bloc_data = self.builder.commit(name, abs_week)
        
        # Use the controller method that accepts the payload dict
        success = self.controller.create_shooting_bloc(**bloc_data)
        
        if success:
            self.view.commit_and_close()