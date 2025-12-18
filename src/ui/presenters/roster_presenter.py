import logging

from PyQt6.QtCore import pyqtSlot, QPoint

from core.interfaces import IGameController
from data.game_state import Talent
from ui.presenters.base_presenter import BasePresenter
from ui.models.roster_view_model import RosterViewModel
from ui.models.roster_table_model import RosterTableModel
from utils import time_utils

logger = logging.getLogger(__name__)

class RosterPresenter(BasePresenter):
    """
    Presenter for the RosterWindow.
    Handles data fetching, formatting, and view interactions.
    """
    def __init__(self, controller: IGameController, view, ui_manager, parent=None):
        super().__init__(controller, view, parent)
        self.ui_manager = ui_manager
        
        self._setup_view_connections()
        self._initialize_view_state()
        self.refresh_data()

    def _setup_view_connections(self):
        """Connects View signals to Presenter slots."""
        # Use standard connect() for View signals (auto-cleanup on view destruction)
        
        # Navigation
        self.view.profile_requested.connect(self._on_profile_requested)
        self.view.help_btn.help_requested.connect(self.controller.signals.show_help_requested.emit)
         
        # Hover / Smart Table
        self.view.smart_hover_entered.connect(self._on_table_hover)
        self.view.smart_hover_left.connect(self.ui_manager.hide_talent_summary)
         
        # Column Visibility
        self.view.column_visibility_changed.connect(self._on_column_visibility_changed)
         
        # Data Updates (Auto-refresh when game week changes or new contracts signed)
        # Use connect_signal() for Controller signals (requires manual cleanup)
        self.connect_signal(self.controller.signals.time_changed, self.refresh_data)
        self.connect_signal(self.controller.signals.talent_pool_changed, self.refresh_data)

    @pyqtSlot(object, QPoint)
    def _on_table_hover(self, data_obj, pos: QPoint):
        """Extracts the ID from the table model's data object and shows summary."""
        # In RosterTableModel, the UserRole is the TalentDB object
        if hasattr(data_obj, 'id'):
            self.ui_manager.show_talent_summary(data_obj.id, pos)

    def _initialize_view_state(self):
        """Loads column visibility settings and configures the View Menu."""
        settings = self.controller.settings_manager.get_setting("roster_visible_columns", {})
        
        # Define toggleable columns (Alias is always visible)
        # Structure: key -> (ModelColumnIndex, DefaultVisible, DisplayName)
        self.columns_config = {
            "salary": (RosterTableModel.COL_SALARY, True, "Salary"),
            "duration": (RosterTableModel.COL_DURATION, True, "Duration Left"),
            "compliance": (RosterTableModel.COL_COMPLIANCE, True, "Compliance"),
            "dates": (RosterTableModel.COL_DATES, False, "Start/End Dates"),
            "usage": (RosterTableModel.COL_USAGE, True, "Monthly Usage"),
            "orientations": (RosterTableModel.COL_ORIENTATIONS, False, "Orientations"),
            "concepts": (RosterTableModel.COL_CONCEPTS, False, "Concepts"),
            "dyn_disp": (RosterTableModel.COL_DYN_DISP, True, "Dyn / Disp"),
        }
        
        menu_items = []
        for key, (col_idx, default, name) in self.columns_config.items():
            is_visible = settings.get(key, default)
            
            # Apply state to View immediately
            self.view.set_column_hidden(col_idx, not is_visible)
            
            # Build menu item dict
            menu_items.append({
                'key': key,
                'name': name,
                'visible': is_visible
            })
            
        self.view.configure_view_menu(menu_items)

    @pyqtSlot()
    def refresh_data(self):
        """Fetches fresh data and repopulates the table model."""
        if not self.view:
             return

        talents_db = self.controller.get_contracted_talents()
        talent_ids = [t.id for t in talents_db]
        
        # Single query
        usage_map = self.controller.get_contracted_scene_counts_bulk(talent_ids)

        view_models = []
        current_week = self.controller.game_state.absolute_week
        
        for talent in talents_db:
            if not talent.contract:
                continue
                
            contract = talent.contract
            
            # -- Calculations --
            # Dates
            start_str = time_utils.format_year_month_week(contract.start_absolute_week)
            end_str = time_utils.format_year_month_week(contract.end_absolute_week)
            weeks_left = max(0, contract.end_absolute_week - current_week)
            
            # Usage
            used_count = usage_map.get(talent.id, 0) 
            max_count = contract.max_scenes_per_month
            usage_str = f"{used_count}/{max_count}"
            usage_ratio = used_count / max_count if max_count > 0 else 0
            
            # Formatting Strings
            orientations = ", ".join(contract.allowed_orientations) if contract.allowed_orientations else "None"
            concepts = ", ".join(contract.allowed_concepts) if contract.allowed_concepts else "None"
            
            dyn_disp_parts = []
            if contract.max_dynamic:
                 dyn_disp_parts.append(f"Lvl {contract.max_dynamic}")
            if contract.disposition:
                 dyn_disp_parts.append(contract.disposition)
            dyn_disp_str = " / ".join(dyn_disp_parts)

            vm = RosterViewModel(
                talent_id=talent.id,
                talent_obj=talent.to_dataclass(Talent), 
                alias=talent.alias,
                
                salary_display=f"${contract.weekly_salary:,}",
                salary_sort=contract.weekly_salary,
                
                duration_left_display=f"{weeks_left}w",
                duration_left_sort=weeks_left,
                
                compliance_display=f"{contract.compliance}%",
                compliance_sort=contract.compliance,
                
                dates_display=f"{start_str} - {end_str}",
                start_week_sort=contract.start_absolute_week,
                
                usage_display=usage_str,
                usage_sort=usage_ratio,
                
                allowed_orientations=orientations,
                allowed_concepts=concepts,
                limits_dynamic_disposition=dyn_disp_str
            )
            view_models.append(vm)

        self.view.table_model.set_data(view_models)

    @pyqtSlot(str, bool)
    def _on_column_visibility_changed(self, key: str, is_visible: bool):
        """Updates view and saves setting."""
        if key in self.columns_config:
            col_idx = self.columns_config[key][0]
            self.view.set_column_hidden(col_idx, not is_visible)
            
            # Save to settings
            current_settings = self.controller.settings_manager.get_setting("roster_visible_columns", {})
            current_settings[key] = is_visible
            self.controller.settings_manager.set_setting("roster_visible_columns", current_settings)

    @pyqtSlot(int)
    def _on_profile_requested(self, talent_id: int):
        self.ui_manager.show_talent_profile_by_id(talent_id)