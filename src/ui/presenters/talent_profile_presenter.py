import logging
from typing import TYPE_CHECKING
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal
from PyQt6 import sip

from data.game_state import Talent
from core.interfaces import IGameController
from ui.views.talent_profile_view import TalentProfileWindow

# Sub-Presenters
from ui.presenters.talent_profile.details_presenter import DetailsPresenter
from ui.presenters.talent_profile.schedule_presenter import SchedulePresenter
from ui.presenters.talent_profile.preferences_presenter import PreferencesPresenter
from ui.presenters.talent_profile.history_presenter import HistoryPresenter
from ui.presenters.talent_profile.chemistry_presenter import ChemistryPresenter
from ui.presenters.talent_profile.hiring_presenter import HiringPresenter

if TYPE_CHECKING:
    from ui.managers.ui_manager import UIManager

logger = logging.getLogger(__name__)

# Constants for bottom tab indices
TAB_IDX_HISTORY = 0
TAB_IDX_CHEMISTRY = 1

class TalentProfilePresenter(QObject):
    """
    Coordinator Presenter for the TalentProfileWindow.
    Manages tab state and delegates specific tab logic to sub-presenters.
    """
    open_talent_profile_requested = pyqtSignal(int)

    def __init__(self, controller: IGameController, view: TalentProfileWindow, uimanager: 'UIManager', parent=None):
        super().__init__(parent)
        self.controller = controller
        self.view = view
        self.uimanager = uimanager
        
        self.open_talents = {}  # {talent_id: Talent}
        self.current_talent_id = None

        # Tracking dirty state for heavy tabs {talent_id: {tab_idx: bool}}
        # If an entry is True, that tab needs reloading when it becomes visible.
        self._heavy_tabs_dirty = {} 

        # Initialize Sub-Presenters
        self.details_presenter = DetailsPresenter(controller, view.details_widget, parent=self)
        self.schedule_presenter = SchedulePresenter(controller, view.schedule_widget, parent=self)
        self.preferences_presenter = PreferencesPresenter(controller, view.preferences_widget, parent=self)
        self.history_presenter = HistoryPresenter(controller, view.history_widget, uimanager, parent=self)
        self.chemistry_presenter = ChemistryPresenter(controller, view.chemistry_widget, uimanager, parent=self)
        # HiringPresenter needs the view as a parent for dialogs
        self.hiring_presenter = HiringPresenter(controller, view.hiring_widget, uimanager, view_parent=view, parent=self)

        self._connect_global_signals()

        # Connect local view signals
        self.view.bottom_tab_changed.connect(self._on_bottom_tab_changed)
        
        # Initial Theme Setup
        current_theme_name = self.controller.settings_manager.get_setting("theme", "light")
        current_theme = self.controller.theme_manager.get_theme(current_theme_name)
        self._apply_theme_colors(current_theme.danger)

        # Ensure cleanup when view is destroyed
        self.view.destroyed.connect(self.cleanup)

    def _connect_global_signals(self):
        """Connects to global controller/settings signals."""
        self.controller.signals.scenes_changed.connect(self._refresh_current_talent_data_on_change)
        self.controller.signals.roster_changed.connect(self._refresh_current_talent_data_on_change)
        self.controller.settings_manager.signals.setting_changed.connect(self._on_setting_changed)

    def cleanup(self):
        """Disconnects global signals to prevent zombie callbacks."""
        try:
            self.controller.signals.scenes_changed.disconnect(self._refresh_current_talent_data_on_change)
        except (RuntimeError, TypeError): pass
            
        try:
            self.controller.signals.roster_changed.disconnect(self._refresh_current_talent_data_on_change)
        except (RuntimeError, TypeError): pass

        try:
            self.controller.settings_manager.signals.setting_changed.disconnect(self._on_setting_changed)
        except (RuntimeError, TypeError): pass

    def open_talent(self, talent: Talent):
        """Opens a talent in the window, creating a new tab if necessary."""
        if talent.id in self.open_talents:
            self.switch_to_talent(talent.id)
        else:
            self.open_talents[talent.id] = talent
            self.view.add_talent_tab(talent.id, talent.alias)
            self.switch_to_talent(talent.id)

    def switch_to_talent(self, talent_id: int):
        """Switches the view to display data for the given talent_id."""
        if self.current_talent_id == talent_id:
            return
        if talent_id not in self.open_talents:
            return

        self.current_talent_id = talent_id
        self.view.set_active_talent_tab(talent_id)
        self._load_data_for_current_talent()

    def close_talent(self, talent_id: int):
        """Closes a talent's tab and removes it from the open list."""
        if talent_id not in self.open_talents:
            return

        del self.open_talents[talent_id]
        self.view.remove_talent_tab(talent_id)

        # Cleanup dirty state tracking
        if talent_id in self._heavy_tabs_dirty:
            del self._heavy_tabs_dirty[talent_id]

        if not self.open_talents:
            self.current_talent_id = None
            # Optionally close window here, usually handled by UI Manager or user action
            self.view.close()
        elif self.current_talent_id == talent_id:
            self.current_talent_id = None
            # Logic to switch to adjacent tab could go here if View doesn't handle it

    def _load_data_for_current_talent(self):
        """Delegates data loading to all sub-presenters."""
        if not self.current_talent_id or self.current_talent_id not in self.open_talents:
            return
            
        talent = self.open_talents[self.current_talent_id]

        # Mark heavy tabs as dirty for this talent so they load when viewed
        self._mark_heavy_tabs_dirty(self.current_talent_id)

        # Load "Core" tabs immediately (Fast/Always Visible)
        self.details_presenter.set_talent(talent)
        self.schedule_presenter.set_talent(talent)
        self.preferences_presenter.set_talent(talent)
        self.hiring_presenter.set_talent(talent)

        # Trigger load for whichever heavy tab is currently visible
        self._load_visible_heavy_tab()

    def _refresh_current_talent_data_on_change(self):
        """Refreshes dynamic data when game state changes."""
        if not self.view or sip.isdeleted(self.view):
            return

        if self.current_talent_id:
            # Refresh the talent object reference
            updated_talent = self.controller.get_talent_by_id(self.current_talent_id)
            if updated_talent:
                self.open_talents[self.current_talent_id] = updated_talent
                
                # Update sub-presenters that display dynamic data
                self.schedule_presenter.set_talent(updated_talent)
                self.hiring_presenter.set_talent(updated_talent)
                self.details_presenter.set_talent(updated_talent) # Fatigue/Stats might change

                # Mark heavy tabs dirty and reload visible one
                self._mark_heavy_tabs_dirty(self.current_talent_id)
                self._load_visible_heavy_tab()

    def _mark_heavy_tabs_dirty(self, talent_id: int):
        """Resets the dirty flags for heavy tabs."""
        self._heavy_tabs_dirty[talent_id] = {
            TAB_IDX_HISTORY: True,
            TAB_IDX_CHEMISTRY: True
        }

    @pyqtSlot(int)
    def _on_bottom_tab_changed(self, index: int):
        """Handle user switching the bottom tab (History vs Chemistry)."""
        self._load_visible_heavy_tab()

    def _load_visible_heavy_tab(self):
        """Checks the currently visible bottom tab and loads its data if dirty."""
        if not self.current_talent_id or self.current_talent_id not in self.open_talents:
            return

        # Ensure we have a tracking dict for this talent
        if self.current_talent_id not in self._heavy_tabs_dirty:
            self._mark_heavy_tabs_dirty(self.current_talent_id)

        talent = self.open_talents[self.current_talent_id]
        dirty_flags = self._heavy_tabs_dirty[self.current_talent_id]
        current_tab_idx = self.view.get_active_bottom_tab_index()

        if current_tab_idx == TAB_IDX_HISTORY:
            if dirty_flags.get(TAB_IDX_HISTORY, False):
                self.history_presenter.set_talent(talent)
                dirty_flags[TAB_IDX_HISTORY] = False
                
        elif current_tab_idx == TAB_IDX_CHEMISTRY:
            if dirty_flags.get(TAB_IDX_CHEMISTRY, False):
                self.chemistry_presenter.set_talent(talent)
                dirty_flags[TAB_IDX_CHEMISTRY] = False

    def _apply_theme_colors(self, danger_color: str):
        """Propagates theme colors to relevant sub-presenters."""
        self.preferences_presenter.handle_theme_change(danger_color)
        self.hiring_presenter.handle_theme_change(danger_color)

    @pyqtSlot(str)
    def _on_setting_changed(self, key: str):
        if not self.view or sip.isdeleted(self.view):
            return

        if key == "unit_system":
            # Refresh details to update physical stats format
            if self.current_talent_id:
                talent = self.open_talents[self.current_talent_id]
                self.details_presenter.set_talent(talent)
                
        elif key == "theme" or key == "font_size":
            current_theme = self.controller.theme_manager.get_theme(
                self.controller.settings_manager.get_setting("theme", "light")
            )
            self._apply_theme_colors(current_theme.danger)
            # Re-load data to ensure any styled text (like HTML tooltips) is regenerated
            self._load_data_for_current_talent()