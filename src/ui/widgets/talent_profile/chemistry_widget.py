from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QTableWidget,
    QTableWidgetItem, QAbstractItemView
)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt, pyqtSignal

from utils.formatters import CHEMISTRY_MAP

class ChemistryWidget(QWidget):
    """A widget for displaying a talent's chemistry with other talent."""
    talent_profile_requested = pyqtSignal(int)  # other_talent_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        chemistry_group = QGroupBox("Chemistry")
        chemistry_layout = QVBoxLayout(chemistry_group)
        self.chemistry_table = QTableWidget()
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
    
    def _on_chemistry_double_clicked(self, item: QTableWidgetItem):
        # We only care about clicks in the first column (talent alias)
        if item.column() == 0:
            if talent_id := self.chemistry_table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole):
                self.talent_profile_requested.emit(talent_id)

    def display_chemistry(self, chemistry_data: list):
        self.chemistry_table.setRowCount(0) # Clear table before populating
        self.chemistry_table.setRowCount(len(chemistry_data))
        for row, chem_info in enumerate(chemistry_data):
            score = chem_info['score']
            display_text, color = CHEMISTRY_MAP.get(score, ("Unknown", QColor("black")))
            
            alias_item = QTableWidgetItem(chem_info['other_talent_alias'])
            alias_item.setData(Qt.ItemDataRole.UserRole, chem_info['other_talent_id'])

            chem_item = QTableWidgetItem(display_text)
            chem_item.setForeground(color)
            chem_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.chemistry_table.setItem(row, 0, alias_item)
            self.chemistry_table.setItem(row, 1, chem_item)
        
        self.chemistry_table.resizeColumnsToContents()