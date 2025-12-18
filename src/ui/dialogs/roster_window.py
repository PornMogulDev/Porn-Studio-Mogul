from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QHeaderView, QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QSize

from ui.dialogs.base_game_window import BaseGameWindow
from ui.widgets.buttons.help_button import HelpButton
from ui.widgets.buttons.view_menu_button import ViewMenuButton
from ui.widgets.entity_card.smart_table_view import SmartTableView
from ui.models.roster_table_model import RosterTableModel

class RosterWindow(BaseGameWindow):
    """
    Dialog for displaying the roster of contracted talent.
    Shows details like salary, compliance, and scene usage.
    """
    # Signals for the Presenter to handle
    column_visibility_changed = pyqtSignal(str, bool)
    smart_hover_entered = pyqtSignal(object, QPoint)
    smart_hover_left = pyqtSignal()
    profile_requested = pyqtSignal(int) # Emits talent_id

    def __init__(self, settings_manager, icon_manager, theme_manager, parent=None):
        self.defaultSize = QSize(1000, 600)
        super().__init__(settings_manager, parent)
        self.icon_manager = icon_manager
        self.theme_manager = theme_manager
        
        # Set window properties
        self.setWindowTitle("Exclusive Roster")
        
        self._setup_ui()
        self._setup_table_behavior()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- Top Bar ---
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        title_label = QLabel("Active Contracts")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        top_bar_layout.addWidget(title_label)
        
        top_bar_layout.addStretch()
        
        # View Menu (Column Toggler)
        self.view_menu_btn = ViewMenuButton(self.icon_manager, self)
        # We forward the signal to the presenter
        self.view_menu_btn.visibility_changed.connect(self.column_visibility_changed.emit)
        top_bar_layout.addWidget(self.view_menu_btn)
        
        # Help Button
        self.help_btn = HelpButton("overview", self.icon_manager, self)
        top_bar_layout.addWidget(self.help_btn)

        main_layout.addLayout(top_bar_layout)

        # --- Main Table ---
        self.table_view = SmartTableView(parent=self)
        self.table_model = RosterTableModel(self.theme_manager, self.settings_manager, parent=self)
        self.table_view.setModel(self.table_model)
        
        # Table Styling
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(SmartTableView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(SmartTableView.SelectionMode.SingleSelection)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.horizontalHeader().setStretchLastSection(False)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        # Enable sorting
        self.table_view.setSortingEnabled(True)

        # Configure Header Sizes
        self._configure_header_sizes()

        main_layout.addWidget(self.table_view)

    def _configure_header_sizes(self):
        """Sets the default widths for columns."""
        header = self.table_view.horizontalHeader()
        
        # Allow user to resize columns by default
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        
        # Set specific pixel widths for data columns
        header.resizeSection(RosterTableModel.COL_ALIAS, 175)
        header.resizeSection(RosterTableModel.COL_SALARY, 120)
        header.resizeSection(RosterTableModel.COL_DURATION, 60)
        header.resizeSection(RosterTableModel.COL_COMPLIANCE, 75)
        header.resizeSection(RosterTableModel.COL_START_DATE, 100)
        header.resizeSection(RosterTableModel.COL_END_DATE, 100)
        header.resizeSection(RosterTableModel.COL_USAGE, 120)
        header.resizeSection(RosterTableModel.COL_ORIENTATIONS, 150)
        header.resizeSection(RosterTableModel.COL_CONCEPTS, 150)
        header.resizeSection(RosterTableModel.COL_DYN_DISP, 100)

    def _setup_table_behavior(self):
        """Wires up the smart table interactions."""
        # 1. Smart Hover (Entity Card)
        # Configure which columns trigger the hover (Alias only, column 0)
        self.table_view.set_smart_columns([0])
        
        self.table_view.smart_hover_entered.connect(self.smart_hover_entered.emit)
        self.table_view.smart_hover_left.connect(self.smart_hover_left.emit)
        
        # 2. Alt+Click (Open Profile)
        self.table_view.smart_alt_clicked.connect(self._on_talent_interaction)
        
        # 3. Double Click (Open Profile)
        self.table_view.doubleClicked.connect(self._on_table_double_clicked)

    def _on_talent_interaction(self, talent_obj):
        """Helper to extract ID and emit signal."""
        if hasattr(talent_obj, 'id'):
            self.profile_requested.emit(talent_obj.id)

    def _on_table_double_clicked(self, index):
        """Extracts UserRole object (Talent) and requests profile."""
        if not index.isValid():
            return
            
        # Get data from the Alias column (UserRole holds the object)
        # We map to the source model index in case sorting is active (though QTableView handles this usually)
        talent_obj = index.sibling(index.row(), 0).data(Qt.ItemDataRole.UserRole)
        self._on_talent_interaction(talent_obj)

    def set_column_hidden(self, col_index: int, hidden: bool):
        """Proxy method to hide/show columns in the table view."""
        self.table_view.setColumnHidden(col_index, hidden)

    def configure_view_menu(self, items: list):
        """Passes the configuration list to the ViewMenuButton."""
        self.view_menu_btn.set_items(items)
    
    def update_view_menu_item(self, key: str, visible: bool):
        """Updates internal state of view menu without triggering signals."""
        self.view_menu_btn.update_item_visibility(key, visible)