import logging
from PyQt6.QtWidgets import ( 
    QWidget, QTabBar, QMessageBox, QSplitter, 
    QVBoxLayout, QHBoxLayout, QTabWidget
)
from PyQt6.QtCore import (
    Qt, pyqtSlot, QEvent, QSize, pyqtSignal, QTimer,
    QByteArray
)

from ui.dialogs.base_game_window import BaseGameWindow
from ui.widgets.preset_widget import PresetWidget
from ui.widgets.talent_profile.details_widget import DetailsWidget
from ui.widgets.talent_profile.schedule_widget import ScheduleWidget
from ui.widgets.talent_profile.preferences_widget import PreferencesWidget
from ui.widgets.talent_profile.history_widget import HistoryWidget
from ui.widgets.talent_profile.chemistry_widget import ChemistryWidget
from ui.widgets.talent_profile.hiring_widget import HiringWidget
from ui.dialogs.sponsor_tour_dialog import SponsorTourDialog

logger = logging.getLogger(__name__)

class TalentProfileWindow(BaseGameWindow):
    """
    The main window for displaying talent profiles.
    Refactored to use BaseGameWindow and a nested QSplitter layout.
    """
    # Emitted after the user confirms the tour details in the dialog.
    tour_sponsorship_confirmed = pyqtSignal(int, list, dict, int) # talent_id, roles_to_cast, tour_details, total_cost

    def __init__(self, settings_manager, icon_manager, parent=None):
        super().__init__(settings_manager, parent)
        self.icon_manager = icon_manager
        self.presenter = None # Will be set by UIManager
        self._is_loading_layout = False # Flag to prevent signal loops

        self.defaultSize = QSize(1360, 1200)
        self.setWindowTitle("Talent Profile")

        self._setup_ui()
        self._connect_signals()
    
    # Add showEvent override
    def showEvent(self, event):
        super().showEvent(event)
        if not self._is_loading_layout:
            # Only load if we haven't already (or simple check to prevent overwrite)
            QTimer.singleShot(0, self._load_last_used_layout)

    def _get_window_name(self) -> str:
        """Provides a consistent key for saving settings."""
        return self.__class__.__name__

    def closeEvent(self, event: QEvent):
        """Overridden to save geometry before closing."""
        self._save_geometry() # From GeometryManagerMixin
        # Note: Layout state saving logic removed here; will be handled manually or via splitters in Step 3
        super().closeEvent(event)

    def _setup_ui(self):
        """Initializes the core UI components using a generic layout and splitters."""
        
        # 1. Main Layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 2. Tab Bar Container
        self.tab_container = QWidget()
        tab_layout = QHBoxLayout(self.tab_container)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        self.tab_bar = QTabBar()
        self.tab_bar.setExpanding(True)
        self.tab_bar.setTabsClosable(True)
        self.tab_bar.setMovable(True)

        tab_layout.addWidget(self.tab_bar)

        self.main_layout.addWidget(self.tab_container)

        # 3. Layout Management Container
        self.layout_toolbar = QWidget()
        layout_mgr_layout = QHBoxLayout(self.layout_toolbar)
        layout_mgr_layout.setContentsMargins(5, 5, 5, 5)
        
        self.layout_preset_widget = PresetWidget(label_text="Layout:")

        layout_mgr_layout.addWidget(self.layout_preset_widget)
        layout_mgr_layout.addStretch()

        self.main_layout.addWidget(self.layout_toolbar)

        # 4. Instantiate Widgets
        # Use horizontal layout for the main profile window
        self.details_widget = DetailsWidget(self.settings_manager, self.icon_manager, use_horizontal_layout=True)
        self.preferences_widget = PreferencesWidget()
        self.schedule_widget = ScheduleWidget()
        self.hiring_widget = HiringWidget()
        self.history_widget = HistoryWidget()
        self.chemistry_widget = ChemistryWidget()

        # 5. Splitter Hierarchy
        
        # Left Splitter (Vertical): Details | Preferences
        self.left_splitter = QSplitter(Qt.Orientation.Vertical)
        self.left_splitter.setObjectName("LeftSplitter")
        self.left_splitter.addWidget(self.details_widget)
        self.left_splitter.addWidget(self.preferences_widget)
        # Initial sizes: details larger
        self.left_splitter.setStretchFactor(0, 2)
        self.left_splitter.setStretchFactor(1, 1)

        # Right Splitter (Vertical): Schedule | Hiring
        self.right_splitter = QSplitter(Qt.Orientation.Vertical)
        self.right_splitter.setObjectName("RightSplitter")
        self.right_splitter.addWidget(self.schedule_widget)
        self.right_splitter.addWidget(self.hiring_widget)
        # Initial sizes: schedule larger
        self.right_splitter.setStretchFactor(0, 2)
        self.right_splitter.setStretchFactor(1, 1)

        # Top Splitter (Horizontal): Left Splitter | Right Splitter
        self.top_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.top_splitter.setObjectName("TopSplitter")
        self.top_splitter.addWidget(self.left_splitter)
        self.top_splitter.addWidget(self.right_splitter)
        self.top_splitter.setStretchFactor(0, 1)
        self.top_splitter.setStretchFactor(1, 1)

        # Bottom Tabs: History | Chemistry
        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setObjectName("BottomTabWidget")
        self.bottom_tabs.addTab(self.history_widget, "Scene History")
        self.bottom_tabs.addTab(self.chemistry_widget, "Chemistry")

        # Main Splitter (Vertical): Top Splitter | Bottom Tabs
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_splitter.setObjectName("MainSplitter")
        self.main_splitter.addWidget(self.top_splitter)
        self.main_splitter.addWidget(self.bottom_tabs)
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 1)

        # Add main splitter to layout
        self.main_layout.addWidget(self.main_splitter)

        self._populate_layouts_combobox()

    def _connect_signals(self):
        self.tab_bar.currentChanged.connect(self._on_tab_changed)
        self.tab_bar.tabCloseRequested.connect(self._on_tab_close_requested)
        self.hiring_widget.sponsor_tour_requested.connect(self._on_sponsor_tour_requested)
        self.layout_preset_widget.load_requested.connect(self._load_layout_by_name)
        self.layout_preset_widget.save_requested.connect(self._on_save_layout)
        self.layout_preset_widget.delete_requested.connect(self._on_delete_layout)

    # --- Public methods for Presenter ---
    def add_talent_tab(self, talent_id: int, alias: str):
        """Adds a new tab for a talent if it doesn't exist."""
        # Check if tab for this talent already exists
        for i in range(self.tab_bar.count()):
            if self.tab_bar.tabData(i) == talent_id:
                return # Tab already exists

        # Block signals to prevent the `currentChanged` signal from firing
        # before we have a chance to set the tab's data, which causes a race condition.
        self.tab_bar.blockSignals(True)
        index = self.tab_bar.addTab(alias)
        self.tab_bar.setTabData(index, talent_id)
        self.tab_bar.blockSignals(False)

    def remove_talent_tab(self, talent_id: int):
        """Removes the tab corresponding to the given talent_id."""
        for i in range(self.tab_bar.count()):
            if self.tab_bar.tabData(i) == talent_id:
                self.tab_bar.removeTab(i)
                break

    def set_active_talent_tab(self, talent_id: int):
        """Sets the tab corresponding to the given talent_id as the current one."""
        for i in range(self.tab_bar.count()):
            if self.tab_bar.tabData(i) == talent_id and self.tab_bar.currentIndex() != i:
                self.tab_bar.setCurrentIndex(i)
                break

    # --- Slots for UI signals ---
    @pyqtSlot(int)
    def _on_tab_changed(self, index: int):
        """Slot for when the user clicks a different tab."""
        if self.presenter and index != -1:
            talent_id = self.tab_bar.tabData(index)
            if talent_id:
                self.presenter.switch_to_talent(talent_id)

    @pyqtSlot(int)
    def _on_tab_close_requested(self, index: int):
        """Slot for when the user clicks the 'x' on a tab."""
        if self.presenter and index != -1:
            talent_id = self.tab_bar.tabData(index)
            if talent_id:
                self.presenter.close_talent(talent_id)

    @pyqtSlot(list)
    def _on_sponsor_tour_requested(self, roles_for_tour: list):
        """
        Handles the request from the HiringWidget to sponsor a tour.
        This method manages the entire UI flow for the negotiation.
        """
        if not self.presenter or not self.presenter.current_talent_id:
            return

        # 1. Ask the presenter to fetch and prepare the preview data.
        preview_data_dict = self.presenter.get_tour_sponsorship_preview(roles_for_tour)

        # 2. Handle the case where the tour is not feasible.
        if not preview_data_dict.get('is_feasible'):
            reason = preview_data_dict.get('refusal_reason', "Unknown reason.")
            QMessageBox.warning(self, "Tour Infeasible", f"Cannot sponsor this tour: {reason}")
            return

        # 3. Create and show the negotiation dialog.
        talent_alias = self.presenter.open_talents[self.presenter.current_talent_id].alias
        dialog = SponsorTourDialog(talent_alias, preview_data_dict, self)

        # 4. Connect logic to the dialog's confirmation signal.
        # This runs synchronously while the dialog is visible but in "Processing" state.
        def on_tour_confirmed():
            final_tour_details = dialog.get_selected_tour_details()
            if final_tour_details:
                total_cost = dialog.get_final_cost()
                self.tour_sponsorship_confirmed.emit(
                    self.presenter.current_talent_id, roles_for_tour,
                    final_tour_details, total_cost
                )
        
        dialog.tour_confirmed.connect(on_tour_confirmed)

        # 5. Show the dialog.
        dialog.exec()

    # --- Layout Management ---
    def _populate_layouts_combobox(self):
        """Loads saved layout names into the combobox."""
        layouts = self.settings_manager.get_talent_profile_layouts()
        current_layout = self.settings_manager.get_setting("talent_profile_last_layout")
        preset_list = list(layouts.keys()) if layouts else []
        self.layout_preset_widget.populate_presets(preset_list, current_selection=current_layout)
        

    def _load_last_used_layout(self):
        """Loads the last layout that was active in the previous session."""
        last_layout_name = self.settings_manager.get_setting("talent_profile_last_layout")
        if last_layout_name:
            # Logic: We attempt to load it. The UI (combobox) is already updated 
            # via _populate_layouts_combobox called in _setup_ui -> init.
            self._load_layout_by_name(last_layout_name)

    @pyqtSlot(str)
    def _on_save_layout(self, layout_name: str):
        """Saves the current splitter configuration to the settings."""
        # layout_name comes directly from the widget signal
        
        if not layout_name:
            QMessageBox.warning(self, "Save Layout", "Please enter a name for the layout.")
            return

        # Capture layout state using QByteArray for robustness
        layout_data = {
            "main": self.main_splitter.saveState().toBase64().data().decode('ascii'),
            "top": self.top_splitter.saveState().toBase64().data().decode('ascii'),
            "left": self.left_splitter.saveState().toBase64().data().decode('ascii'),
            "right": self.right_splitter.saveState().toBase64().data().decode('ascii'),
            "bottom_tab": self.bottom_tabs.currentIndex()
        }

        layouts = self.settings_manager.get_talent_profile_layouts()
        layouts[layout_name] = layout_data
        self.settings_manager.set_talent_profile_layouts(layouts)
        
        # Refresh list and re-select the saved layout
        self._populate_layouts_combobox()

        QMessageBox.information(self, "Layout Saved", f"Layout '{layout_name}' has been saved.")

    @pyqtSlot(str)
    def _on_delete_layout(self, layout_name: str):
        """Deletes the currently selected layout from settings."""
        if not layout_name:
            return

        reply = QMessageBox.question(self, "Delete Layout", 
                                     f"Are you sure you want to delete the layout '{layout_name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            layouts = self.settings_manager.get_talent_profile_layouts()
            if layout_name in layouts:
                del layouts[layout_name]
                self.settings_manager.set_talent_profile_layouts(layouts)
                self._populate_layouts_combobox()

    @pyqtSlot(str)
    def _load_layout_by_name(self, layout_name: str):
        """
        Loads and applies a layout state from settings based on its name.
        Handles new dict-based layouts and ignores legacy byte strings.
        """
        layouts = self.settings_manager.get_talent_profile_layouts()
        data = layouts.get(layout_name)
        
        if not data:
            logger.warning(f"Could not find layout data for name '{layout_name}' in settings.")
            return

        try:
            # Helper to restore state or fallback to sizes if legacy data
            def restore_splitter(splitter: QSplitter, key: str):
                if key in data:
                    val = data[key]
                    if isinstance(val, str):
                        # New format: Base64 string
                        splitter.restoreState(QByteArray.fromBase64(val.encode('ascii')))
                    elif isinstance(val, list):
                        # Legacy format: List of sizes
                        splitter.setSizes(val)

            restore_splitter(self.main_splitter, "main")
            restore_splitter(self.top_splitter, "top")
            restore_splitter(self.left_splitter, "left")
            restore_splitter(self.right_splitter, "right")
            if "bottom_tab" in data: 
                self.bottom_tabs.setCurrentIndex(data["bottom_tab"])
            
            self.settings_manager.set_setting("talent_profile_last_layout", layout_name)
            logger.info(f"Successfully loaded layout '{layout_name}'.")
            
        except Exception as e:
            logger.error(f"Error applying layout '{layout_name}': {e}", exc_info=True)
            QMessageBox.critical(self, "Load Error", f"Failed to apply layout '{layout_name}'.")