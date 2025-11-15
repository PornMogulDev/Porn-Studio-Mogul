import logging
from PyQt6.QtWidgets import QMainWindow, QWidget, QMenuBar, QDockWidget
from PyQt6.QtCore import Qt

from ui.panels.talent_filter_panel import TalentFilterPanel
from ui.widgets.hiring_dashboard.talent_table_widget import TalentTableWidget
from ui.widgets.hiring_dashboard.role_details_widget import RoleDetailsWidget

logger = logging.getLogger(__name__)

class HiringDashboardTab(QMainWindow):
    """
    A passive view container for the hiring dashboard.
    This class is responsible for creating and laying out the UI widgets
    (filter panel, talent table, role details) using a dockable interface.
    It does not contain any application logic or instantiate any presenters.
    The coordination of these widgets is handled by the HiringDashboardPresenter.
    """
    def __init__(self, controller, ui_manager, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.ui_manager = ui_manager
        self.settings_manager = controller.settings_manager
        
        self._setup_ui()
        self._create_dock_widgets()
    
    def _setup_ui(self):
        """Initialize the core UI components."""
        # Central widget is not used in a pure dock layout
        self.setDockNestingEnabled(True)
        
        # Create menu bar to show/hide docks
        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)
        self.view_menu = menu_bar.addMenu("&View")
    
    def _create_dock_widgets(self):
        """Create and arrange all dockable widgets."""
        # Talent Filter Panel (Left side)
        self.talent_filter_panel = TalentFilterPanel(
            settings_manager=self.settings_manager,
            ethnicities_hierarchy=self.controller.get_ethnicity_hierarchy(),
            cup_sizes=self.controller.get_available_cup_sizes(),
            nationalities=self.controller.get_available_nationalities(),
            locations_by_region=self.controller.get_locations_by_region(),
            go_to_categories=self.controller.get_go_to_list_categories()
        )
        filter_dock = self._add_dock(
            "Talent Filters",
            self.talent_filter_panel,
            Qt.DockWidgetArea.LeftDockWidgetArea
        )
        
        # Role Details (Top Right)
        self.role_details_widget = RoleDetailsWidget()
        role_details_dock = self._add_dock(
            "Role Details",
            self.role_details_widget,
            Qt.DockWidgetArea.RightDockWidgetArea
        )
        
        # Talent Table (Bottom Right)
        self.talent_table_widget = TalentTableWidget()
        talent_table_dock = self._add_dock(
            "Available Talent",
            self.talent_table_widget,
            Qt.DockWidgetArea.RightDockWidgetArea
        )

    def _add_dock(self, title: str, widget: QWidget, area: Qt.DockWidgetArea) -> QDockWidget:
        """Helper to create and add a dock widget."""
        dock = QDockWidget(title, self)
        safe_name = title.replace(' & ', 'And').replace(' ', '')
        dock.setObjectName(f"{safe_name}DockWidget")
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        self.view_menu.addAction(dock.toggleViewAction())
        return dock