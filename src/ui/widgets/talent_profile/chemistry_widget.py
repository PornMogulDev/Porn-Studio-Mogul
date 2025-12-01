from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QTableWidget,
    QTableWidgetItem, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from utils.formatters import get_chemistry_status
from ui.widgets.entity_card.smart_table_widget import SmartTableWidget

class ChemistryWidget(QWidget):
    """A widget for displaying a talent's chemistry with other talent."""
    talent_profile_requested = pyqtSignal(int)  # other_talent_id
    
    # New Smart Signals
    smart_hover_entered = pyqtSignal(object, QPoint)
    smart_hover_left = pyqtSignal()
    smart_alt_clicked = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        chemistry_group = QGroupBox("Chemistry")
        chemistry_layout = QVBoxLayout(chemistry_group)
        self.chemistry_table = SmartTableWidget()
        self.chemistry_table.setColumnCount(2)
        self.chemistry_table.setHorizontalHeaderLabels(["Talent", "Chemistry"])
        self.chemistry_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.chemistry_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.chemistry_table.verticalHeader().setVisible(False)
        self.chemistry_table.horizontalHeader().setStretchLastSection(True)
        chemistry_layout.addWidget(self.chemistry_table)
        main_layout.addWidget(chemistry_group)

    def _connect_signals(self):
        self.chemistry_table.itemDoubleClicked.connect(self._on_chemistry_double_clicked)
        # Connect SmartTable signals to Widget signals
        self.chemistry_table.smart_hover_entered.connect(self.smart_hover_entered)
        self.chemistry_table.smart_hover_left.connect(self.smart_hover_left)
        self.chemistry_table.smart_alt_clicked.connect(self.smart_alt_clicked)
    
    def _on_chemistry_double_clicked(self, item: QTableWidgetItem):
        # We only care about clicks in the first column (talent alias)
        if item.column() == 0:
            if talent_id := self.chemistry_table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole):
                self.talent_profile_requested.emit(talent_id)

    def display_chemistry(self, chemistry_data: list):
        self.chemistry_table.setRowCount(0) # Clear table before populating
        if not chemistry_data:
            return

        self.chemistry_table.setRowCount(len(chemistry_data))
        for row, chem_info in enumerate(chemistry_data):
            status, display_text = get_chemistry_status(chem_info['score'])
             
            alias_item = QTableWidgetItem(chem_info['other_talent_alias'])
            alias_item.setData(Qt.ItemDataRole.UserRole, chem_info['other_talent_id'])
 
            chem_item = QTableWidgetItem(display_text)
            # Set the property that the stylesheet will use for coloring
            chem_item.setData(Qt.ItemDataRole.UserRole, status) # Store for potential future use
            chem_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
 
            self.chemistry_table.setItem(row, 0, alias_item)
            self.chemistry_table.setItem(row, 1, chem_item)
        
        self.chemistry_table.resizeColumnsToContents()