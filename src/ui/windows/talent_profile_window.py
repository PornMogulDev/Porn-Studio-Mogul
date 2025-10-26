from PyQt6.QtWidgets import ( 
    QMainWindow, QWidget, QMenuBar, QDockWidget, QToolBar, QTabBar,
    QHBoxLayout, QLabel, QComboBox, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSlot, QEvent, QByteArray

from ui.mixins.geometry_manager_mixin import GeometryManagerMixin
from ui.widgets.talent_profile.details_widget import DetailsWidget
from ui.widgets.talent_profile.affinities_widget import AffinitiesWidget
from ui.widgets.talent_profile.preferences_widget import PreferencesWidget
from ui.widgets.talent_profile.history_widget import HistoryWidget
from ui.widgets.talent_profile.chemistry_widget import ChemistryWidget
from ui.widgets.talent_profile.hiring_widget import HiringWidget

class TalentProfileWindow(GeometryManagerMixin, QMainWindow):
    """
    The main window for displaying talent profiles.
    Uses a QMainWindow to support a dockable, customizable layout.
    """
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.presenter = None # Will be set by UIManager
        self._is_loading_layout = False # Flag to prevent signal loops

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMinimumSize(800, 600)
        self.setWindowTitle("Talent Profile")

        self._setup_ui()
        self._connect_signals()
        self._restore_geometry()
        self._load_last_used_layout()

    def _get_window_name(self) -> str:
        """Provides a consistent key for saving settings."""
        return self.__class__.__name__

    def closeEvent(self, event: QEvent):
        """Overridden to save both geometry and layout state before closing."""
        self._save_geometry() # From GeometryManagerMixin
        super().closeEvent(event)

    def _setup_ui(self):
        """Initializes the core UI components of the main window."""
        # QMainWindow requires a central widget, even if it's just a placeholder.
        # The dock widgets will be arranged around it.
        self.setCentralWidget(QWidget())

        # The dockNestingEnabled property allows dock widgets to be tabbed together.
        self.setDockNestingEnabled(True)
        
        # Create the main menu bar
        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)
        
        # Add a "View" menu, which will later hold actions to show/hide docks.
        self.view_menu = menu_bar.addMenu("&View")

        # Add the tab bar for switching between open talents
        self.tab_toolbar = QToolBar("Talent Tabs")
        self.tab_toolbar.setObjectName("TalentTabToolBar") # For state saving
        self.tab_bar = QTabBar()
        self.tab_bar.setExpanding(True)
        self.tab_bar.setTabsClosable(True)
        self.tab_bar.setMovable(True)
        self.tab_toolbar.addWidget(self.tab_bar)
        self.addToolBar(self.tab_toolbar)

        # Layout management toolbar
        self.layout_toolbar = QToolBar("Layout Management")
        self.layout_toolbar.setObjectName("LayoutManagementToolBar")
        
        self.layout_toolbar.addWidget(QLabel(" Layout: "))
        self.layout_combobox = QComboBox()
        self.layout_combobox.setEditable(True)
        self.layout_combobox.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.layout_combobox.setToolTip("Select a saved layout or type a new name to save.")
        self.layout_toolbar.addWidget(self.layout_combobox)

        self.save_layout_button = QPushButton("Save")
        self.layout_toolbar.addWidget(self.save_layout_button)

        self.delete_layout_button = QPushButton("Delete")
        self.layout_toolbar.addWidget(self.delete_layout_button)
        self.addToolBarBreak()
        self.addToolBar(self.layout_toolbar)

        self._create_dock_widgets()
        self._populate_layouts_combobox()

    def _connect_signals(self):
        self.tab_bar.currentChanged.connect(self._on_tab_changed)
        self.tab_bar.tabCloseRequested.connect(self._on_tab_close_requested)
        self.save_layout_button.clicked.connect(self._on_save_layout)
        self.delete_layout_button.clicked.connect(self._on_delete_layout)
        self.layout_combobox.currentTextChanged.connect(self._on_load_layout)

    def _create_dock_widgets(self):
        """Creates and arranges all the dockable panel widgets."""
        self.details_widget = DetailsWidget(self.settings_manager)
        self._add_dock("Details & Skills", self.details_widget, Qt.DockWidgetArea.LeftDockWidgetArea)

        self.affinities_widget = AffinitiesWidget()
        self._add_dock("Affinities", self.affinities_widget, Qt.DockWidgetArea.LeftDockWidgetArea)

        self.preferences_widget = PreferencesWidget()
        self._add_dock("Preferences", self.preferences_widget, Qt.DockWidgetArea.RightDockWidgetArea)

        self.hiring_widget = HiringWidget()
        self._add_dock("Hiring", self.hiring_widget, Qt.DockWidgetArea.RightDockWidgetArea)
        
        self.history_widget = HistoryWidget()
        history_dock = self._add_dock("Scene History", self.history_widget, Qt.DockWidgetArea.BottomDockWidgetArea)
        
        self.chemistry_widget = ChemistryWidget()
        chem_dock = self._add_dock("Chemistry", self.chemistry_widget, Qt.DockWidgetArea.BottomDockWidgetArea)
        
        # Tabify the history and chemistry docks by default
        self.tabifyDockWidget(history_dock, chem_dock)
        history_dock.raise_() # Make history the default visible tab

    def _add_dock(self, title: str, widget: QWidget, area: Qt.DockWidgetArea) -> QDockWidget:
        """Helper function to create, add, and connect a QDockWidget."""
        dock = QDockWidget(title, self)
        # Set a unique object name for state saving. e.g., "Details&SkillsDockWidget"
        dock.setObjectName(f"{title.replace(' ', '')}DockWidget")
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        self.view_menu.addAction(dock.toggleViewAction())
        return dock

    # --- Public methods for Presenter ---
    def add_talent_tab(self, talent_id: int, alias: str):
        """Adds a new tab for a talent if it doesn't exist."""
        # Check if tab for this talent already exists
        for i in range(self.tab_bar.count()):
            if self.tab_bar.tabData(i) == talent_id and self.tab_bar.currentIndex() != i:
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
            if self.tab_bar.tabData(i) == talent_id:
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

    # --- Layout Management ---
    def _populate_layouts_combobox(self):
        """Loads saved layout names into the combobox."""
        self._is_loading_layout = True # Prevent load signal while populating
        self.layout_combobox.clear()
        layouts = self.settings_manager.get_talent_profile_layouts()
        if layouts:
            self.layout_combobox.addItems(sorted(layouts.keys()))
        self.layout_combobox.setCurrentIndex(-1) # No selection
        self._is_loading_layout = False

    def _load_last_used_layout(self):
        """Loads the last layout that was active in the previous session."""
        last_layout_name = self.settings_manager.get_setting("talent_profile_last_layout")
        if last_layout_name:
            index = self.layout_combobox.findText(last_layout_name)
            if index != -1:
                self.layout_combobox.setCurrentIndex(index)
                # This will trigger _on_load_layout via the signal

    @pyqtSlot()
    def _on_save_layout(self):
        """Saves the current dock layout to the settings."""
        layout_name = self.layout_combobox.currentText()
        if not layout_name:
            QMessageBox.warning(self, "Save Layout", "Please enter a name for the layout.")
            return

        state_bytes = self.saveState().toBase64()
        state_str = state_bytes.data().decode('ascii')

        layouts = self.settings_manager.get_talent_profile_layouts()
        layouts[layout_name] = state_str
        self.settings_manager.set_talent_profile_layouts(layouts)
        
        self._populate_layouts_combobox()
        # Restore the text after repopulating
        self.layout_combobox.setCurrentText(layout_name)

        QMessageBox.information(self, "Layout Saved", f"Layout '{layout_name}' has been saved.")

    @pyqtSlot()
    def _on_delete_layout(self):
        """Deletes the currently selected layout from settings."""
        layout_name = self.layout_combobox.currentText()
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
    def _on_load_layout(self, layout_name: str):
        """Loads a dock layout from settings when selected in the combobox."""
        if self._is_loading_layout or not layout_name:
            return

        layouts = self.settings_manager.get_talent_profile_layouts()
        state_str = layouts.get(layout_name)
        if state_str:
            state_bytes = QByteArray.fromBase64(state_str.encode('ascii'))
            self.restoreState(state_bytes)
            self.settings_manager.set_setting("talent_profile_last_layout", layout_name)