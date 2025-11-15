from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit,
    QTableView, QHeaderView, QLabel
)
from PyQt6.QtCore import pyqtSignal, Qt, QModelIndex
from typing import List, Dict

from ui.models.talent_table_model import TalentTableModel

class HiringTalentTableWidget(QWidget):
    """Widget displaying talent available for hiring.

    This widget is intentionally "dumb" and only manages the table view
    and status label. All filter controls live in a separate widget so the
    presenter can coordinate them for the hiring dashboard.
    """
    talent_selected = pyqtSignal(object)  # Talent
    name_filter_changed = pyqtSignal(str)

    def __init__(self, settings_manager, parent=None):

        super().__init__(parent)
        self.settings_manager = settings_manager
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Name filter (simple text box above the table, similar to other talent views)
        self.name_filter = QLineEdit()
        self.name_filter.setPlaceholderText("Filter by name...")
        self.name_filter.textChanged.connect(self.name_filter_changed.emit)
        layout.addWidget(self.name_filter)
        
        # Talent table
        self.talent_table_view = QTableView()

        self.talent_table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.talent_table_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.talent_table_view.verticalHeader().setVisible(False)
        self.talent_table_view.setSortingEnabled(True)
        self.talent_table_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        layout.addWidget(self.talent_table_view)
        
        # Connect double-click
        self.talent_table_view.doubleClicked.connect(self._on_talent_double_clicked)
        
        # Status label
        self.status_label = QLabel("Select a role to view available talent")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

    def initialize_model(self, cup_size_order):

        """Initialize the table model with dependencies."""
        self.talent_model = TalentTableModel(
            settings_manager=self.settings_manager,
            cup_size_order=cup_size_order,
            mode='casting'
        )
        self.talent_table_view.setModel(self.talent_model)
        self._configure_table_headers()
    
    def _configure_table_headers(self):
        """Configure column widths."""
        header = self.talent_table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Alias
    
    def update_talent_table(self, talent_data: List[Dict]):
        """
        Update table with talent data.
        talent_data: List of dicts with 'talent' and 'demand' keys
        """
        if hasattr(self, 'talent_model'):
            self.talent_model.update_data(talent_data)
            count = len(talent_data)
            self.status_label.setText(f"Showing {count} available talent")
    
    def _on_talent_double_clicked(self, index: QModelIndex):
        """Handle double-click on talent."""
        if talent := self.talent_model.data(index, Qt.ItemDataRole.UserRole):
            self.talent_selected.emit(talent)

    def get_name_filter(self) -> str:
        return self.name_filter.text().strip()