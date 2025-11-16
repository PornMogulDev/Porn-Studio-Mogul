import logging
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QSplitter
from PyQt6.QtCore import Qt

from ui.panels.talent_filter_panel import TalentFilterPanel
from ui.widgets.hiring_dashboard.talent_table_widget import TalentTableWidget
from ui.widgets.hiring_dashboard.role_details_widget import RoleDetailsWidget
from ui.widgets.view_menu_button import ViewMenuButton

logger = logging.getLogger(__name__)

class HiringDashboardTab(QWidget):
    """
    A passive view container for the hiring dashboard using a QSplitter layout.
    This class is responsible for creating the layout structure. The widgets
    and all logic are provided and managed by the HiringDashboardPresenter.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # --- Widget placeholders ---
        # These will be populated by the presenter via set_widgets()
        self.role_details_widget: RoleDetailsWidget = None
        self.talent_filter_panel: TalentFilterPanel = None
        self.talent_table_widget: TalentTableWidget = None
        
        # This view owns the button, but the presenter will configure it
        self.view_options_button: ViewMenuButton = None

        self._setup_layout()

    def _setup_layout(self):
        """Initialize and lay out the core UI containers using QSplitter."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # --- Top controls container ---
        top_controls_layout = QHBoxLayout()
        self.view_options_button = ViewMenuButton(self)
        self.view_options_button.setToolTip("Show/Hide Panels")
        top_controls_layout.addWidget(self.view_options_button)
        top_controls_layout.addStretch()
        main_layout.addLayout(top_controls_layout)

        # --- Main Splitter Layout ---
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        
        # --- Left Side (Vertical Splitter) ---
        self.left_splitter = QSplitter(Qt.Orientation.Vertical, self)
        
        # Widgets will be added to these splitters later by set_widgets()
        self.main_splitter.addWidget(self.left_splitter)
        
        main_layout.addWidget(self.main_splitter)

    def set_widgets(self, role_details: RoleDetailsWidget, talent_filter: TalentFilterPanel, talent_table: TalentTableWidget):
        """
        Populates the layout with widgets created by the presenter.
        """
        self.role_details_widget = role_details
        self.talent_filter_panel = talent_filter
        self.talent_table_widget = talent_table

        # --- Add widgets to the layout ---
        self.left_splitter.addWidget(self.role_details_widget)
        self.left_splitter.addWidget(self.talent_filter_panel)
        self.main_splitter.addWidget(self.talent_table_widget)

        # --- Fine-tune initial layout ---
        self.main_splitter.setSizes([1, 2]) # Left side vs Right side
        self.left_splitter.setSizes([1, 3]) # Role details vs Filters
        self.left_splitter.setStretchFactor(1, 1) # Allow filter panel to grow more
        self.main_splitter.setStretchFactor(1, 1) # Allow table to grow more