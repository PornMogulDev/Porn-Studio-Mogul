from PyQt6.QtWidgets import ( 
    QMainWindow, QWidget, QMenuBar, QDockWidget,
    QToolBar, QTabBar
)
from PyQt6.QtCore import Qt, pyqtSlot, QEvent

from ui.mixins.geometry_manager_mixin import GeometryManagerMixin
from ui.mixins.window_state_manager_mixin import WindowStateManagerMixin
from ui.widgets.talent_profile.details_widget import DetailsWidget
from ui.widgets.talent_profile.affinities_widget import AffinitiesWidget
from ui.widgets.talent_profile.preferences_widget import PreferencesWidget
from ui.widgets.talent_profile.history_widget import HistoryWidget
from ui.widgets.talent_profile.chemistry_widget import ChemistryWidget
from ui.widgets.talent_profile.hiring_widget import HiringWidget

class TalentProfileWindow(GeometryManagerMixin, WindowStateManagerMixin, QMainWindow):
    """
    The main window for displaying talent profiles.
    Uses a QMainWindow to support a dockable, customizable layout.
    """
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.presenter = None # Will be set by UIManager

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMinimumSize(800, 600)
        self.setWindowTitle("Talent Profile")

        self._setup_ui()
        self._connect_signals()
        self._restore_geometry()
        self._restore_state() # From WindowStateManagerMixin

    def _get_window_name(self) -> str:
        """Provides a consistent key for saving settings."""
        return self.__class__.__name__

    def closeEvent(self, event: QEvent):
        """Overridden to save both geometry and layout state before closing."""
        self._save_geometry() # From GeometryManagerMixin
        self._save_state()    # From WindowStateManagerMixin
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

        self._create_dock_widgets()

    def _connect_signals(self):
        self.tab_bar.currentChanged.connect(self._on_tab_changed)
        self.tab_bar.tabCloseRequested.connect(self._on_tab_close_requested)

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