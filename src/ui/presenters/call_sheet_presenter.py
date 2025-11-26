from typing import TYPE_CHECKING
from PyQt6.QtCore import QObject

from services.builders.shooting_bloc_builder import ShootingBlocBuilder
from utils import time_utils

if TYPE_CHECKING:
    from ui.dialogs.call_sheet_dialog import CallSheetDialog
    from core.game_controller import GameController

class CallSheetPresenter(QObject):
    def __init__(self, controller: 'GameController', view: 'CallSheetDialog', parent=None):
        super().__init__(parent)
        self.controller = controller
        self.view = view
        
        # Ask Controller for the initialized tool
        self.builder = self.controller.get_shooting_bloc_builder()
        
        # Cache for UI responsiveness
        self.departments_cache = self.controller.data_manager.production_departments
        self.styles_cache = self.controller.data_manager.visual_styles
        self.locations_cache = self.controller.data_manager.production_locations

    def initialize(self):
        """Called by View after UI setup."""
        # 1. Setup default Logistics
        locations = list(self.locations_cache.values())
        styles = list(self.styles_cache.values())
        self.view.populate_logistics_options(locations, styles)
        
        # 2. Setup Defaults in Builder
        # (Could load last used settings from SettingsManager here)
        current_week = self.controller.game_state.absolute_week
        year, week = time_utils.from_absolute(current_week)
        self.view.set_schedule_values(week, year)
        self.view.spin_num_scenes.setValue(2) # Default

        # 3. Create Sliders dynamically based on Departments JSON
        # Sort by 'crew' then 'resource' for cleaner addition order?
        # Actually view handles column splitting, so order in dict matters less.
        for dept_id, dept_def in self.departments_cache.items():
            self.view.add_department_slider(
                dept_id, 
                dept_def.get('name', dept_id.title()), 
                dept_def.get('type', 'resource')
            )

        # 4. Populate Policies
        all_policies = list(self.controller.data_manager.on_set_policies_data.values())
        # Check active policies from Studio State (Game State)
        active_ids = self.controller.game_state.active_policies
        # Pre-select them in builder
        for pid in active_ids:
            self.builder.toggle_policy(pid, True)
            
        self.view.populate_policies(all_policies, active_ids)

        # 5. Initial Refresh
        self._sync_view_from_builder()

    def _sync_view_from_builder(self):
        """Updates all UI elements to match Builder state."""
        # Update Slider Values & Estimates
        alloc_data = self.builder.get_allocation_data()
        estimates = self.builder.get_estimates()
        self.view.update_sliders(alloc_data, estimates)
        
        # Update Cost Logic
        num_scenes = self.view.get_num_scenes()
        total_budget = self.builder.total_budget
        est_cost = self.builder.get_total_cost(num_scenes)
        self.view.set_budget_values(total_budget, est_cost)
        
        # Update Descriptions
        style = self.styles_cache.get(self.builder.visual_style_id, {})
        loc = self.locations_cache.get(self.builder.location_id, {})
        self.view.update_logistics_info(
            style.get('description', ''),
            loc.get('tags', [])
        )

    # --- Events ---

    def on_allocation_changed(self, dept_id: str, value: float):
        success = self.builder.update_allocation(dept_id, value)
        if success:
            self._sync_view_from_builder()
        else:
            # If failed (e.g. locks preventing it), revert view by syncing
            self._sync_view_from_builder()

    def on_lock_toggled(self, dept_id: str, is_locked: bool):
        self.builder.toggle_lock(dept_id, is_locked)
        self._sync_view_from_builder()

    def on_total_budget_changed(self, value: int):
        self.builder.set_total_budget(value)
        self._sync_view_from_builder()

    def on_location_changed(self, index: int):
        loc_id = self.view.combo_location.currentData()
        if loc_id:
            self.builder.location_id = loc_id
            self._sync_view_from_builder()

    def on_style_changed(self, index: int):
        style_id = self.view.combo_style.currentData()
        if style_id:
            self.builder.visual_style_id = style_id
            self._sync_view_from_builder()

    def on_policy_toggled(self, policy_id: str, checked: bool):
        self.builder.toggle_policy(policy_id, checked)
        self._sync_view_from_builder()
        
    def on_num_scenes_changed(self, value: int):
        # Only affects cost calculation
        self._sync_view_from_builder()

    def on_confirm(self):
        week, year = self.view.get_schedule_values()
        abs_week = time_utils.to_absolute(year, week)
        num_scenes = self.view.get_num_scenes()
        name = self.view.get_name()
        
        # Generate Payload
        bloc_data = self.builder.commit(name, abs_week, num_scenes)
        
        # Use the controller method that accepts the payload dict
        success = self.controller.create_shooting_bloc(**bloc_data)
        
        if success:
            self.view.commit_and_close()