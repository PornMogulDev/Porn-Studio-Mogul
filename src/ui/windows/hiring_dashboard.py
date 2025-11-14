import logging
from PyQt6.QtWidgets import QMainWindow, QWidget, QMenuBar, QDockWidget
from PyQt6.QtCore import Qt, QSize

from ui.widgets.hiring_dashboard.scene_role_selector_widget import SceneRoleSelectorWidget
from ui.widgets.hiring_dashboard.role_details_widget import RoleDetailsWidget
from ui.widgets.hiring_dashboard.talent_table_widget import HiringTalentTableWidget
from ui.widgets.hiring_dashboard.talent_profile_widget import HiringTalentProfileWidget
from ui.presenters.hiring_dashboard_presenter import HiringDashboardPresenter

logger = logging.getLogger(__name__)

class HiringDashboardTab(QMainWindow):
    """
    Unified hiring dashboard that combines scene/role selection,
    talent filtering, and profile viewing in a docked layout.
    """
    def __init__(self, controller, ui_manager, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.ui_manager = ui_manager
        self.settings_manager = controller.settings_manager
        self.presenter = None
        
        self.setWindowTitle("Hiring Dashboard")
        self.defaultSize = QSize(1400, 900)
        
        self._setup_ui()
        self._create_dock_widgets()
        self._create_presenter()
    
    def _setup_ui(self):
        """Initialize the core UI components."""
        # Central widget (hidden, we use docks)
        central_widget = QWidget()
        central_widget.setMaximumSize(0, 0)
        self.setCentralWidget(central_widget)
        
        # Enable dock nesting
        self.setDockNestingEnabled(True)
        
        # Create menu bar
        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)
        self.view_menu = menu_bar.addMenu("&View")
    
    def _create_dock_widgets(self):
        """Create and arrange all dockable widgets."""
        # Scene/Role Selector (top left)
        self.scene_role_widget = SceneRoleSelectorWidget()
        scene_role_dock = self._add_dock(
            "Scene & Role Selection",
            self.scene_role_widget,
            Qt.DockWidgetArea.LeftDockWidgetArea
        )
        
        # Role Details (top right)
        self.role_details_widget = RoleDetailsWidget()
        role_details_dock = self._add_dock(
            "Role Details",
            self.role_details_widget,
            Qt.DockWidgetArea.RightDockWidgetArea
        )
        
        # Talent Table (middle, spanning width)
        self.talent_table_widget = HiringTalentTableWidget(self.settings_manager)
        talent_table_dock = self._add_dock(
            "Available Talent",
            self.talent_table_widget,
            Qt.DockWidgetArea.BottomDockWidgetArea
        )
        
        # Talent Profile (bottom right)
        self.talent_profile_widget = HiringTalentProfileWidget(self.settings_manager)
        talent_profile_dock = self._add_dock(
            "Talent Profile",
            self.talent_profile_widget,
            Qt.DockWidgetArea.RightDockWidgetArea
        )
        
        # Arrange docks: tabify role details with talent profile
        self.tabifyDockWidget(role_details_dock, talent_profile_dock)
        role_details_dock.raise_()  # Show role details by default
    
    def _add_dock(self, title: str, widget: QWidget, area: Qt.DockWidgetArea) -> QDockWidget:
        """Helper to create and add a dock widget."""
        dock = QDockWidget(title, self)
        safe_name = title.replace(' & ', 'And').replace(' ', '')
        dock.setObjectName(f"{safe_name}DockWidget")
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        self.view_menu.addAction(dock.toggleViewAction())
        return dock
    
    def _create_presenter(self):
        """Create the presenter that coordinates all widgets."""
        self.presenter = HiringDashboardPresenter(
            controller=self.controller,
            scene_role_widget=self.scene_role_widget,
            role_details_widget=self.role_details_widget,
            talent_table_widget=self.talent_table_widget,
            talent_profile_widget=self.talent_profile_widget,
            parent=self
        )
        self.presenter.load_initial_data()