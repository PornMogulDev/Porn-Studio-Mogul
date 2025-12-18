from typing import List, Any
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex
from ui.models.roster_view_model import RosterViewModel

class RosterTableModel(QAbstractTableModel):
    """
    Table Model for displaying contracted talent.
    Supports sorting and Smart Hover interaction via UserRole.
    """
    
    # Column Definitions
    COL_ALIAS = 0
    COL_SALARY = 1
    COL_DURATION = 2
    COL_COMPLIANCE = 3
    COL_DATES = 4
    COL_USAGE = 5
    COL_ORIENTATIONS = 6
    COL_CONCEPTS = 7
    COL_DYN_DISP = 8
    
    HEADERS = [
        "Alias", 
        "Weekly Salary", 
        "Duration Left", 
        "Compliance", 
        "Contract Dates", 
        "Scenes This Month",
        "Orientations", 
        "Concepts", 
        "Dyn / Disp"
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: List[RosterViewModel] = []

    def set_data(self, data: List[RosterViewModel]):
        """Replaces the model data and refreshes the view."""
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._data)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(self.HEADERS):
                return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._data)):
            return None

        row_item = self._data[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == self.COL_ALIAS:
                return row_item.alias
            elif col == self.COL_SALARY:
                return row_item.salary_display
            elif col == self.COL_DURATION:
                return row_item.duration_left_display
            elif col == self.COL_COMPLIANCE:
                return row_item.compliance_display
            elif col == self.COL_DATES:
                return row_item.dates_display
            elif col == self.COL_USAGE:
                return row_item.usage_display
            elif col == self.COL_ORIENTATIONS:
                return row_item.allowed_orientations
            elif col == self.COL_CONCEPTS:
                return row_item.allowed_concepts
            elif col == self.COL_DYN_DISP:
                return row_item.limits_dynamic_disposition

        # UserRole is used by SmartTableView for the Hover Card and Alt-Click
        elif role == Qt.ItemDataRole.UserRole:
            if col == self.COL_ALIAS:
                return row_item.talent_obj

        # Text Alignment
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            # Right-align numbers
            if col in (self.COL_SALARY, self.COL_DURATION, self.COL_COMPLIANCE, self.COL_USAGE):
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        
        # Color Formatting (Optional: Highlight low compliance)
        elif role == Qt.ItemDataRole.ForegroundRole:
            if col == self.COL_COMPLIANCE and row_item.compliance_sort < 80:
                 return Qt.GlobalColor.red

        return None

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder):
        """Sorts the data based on the column and order."""
        self.layoutAboutToBeChanged.emit()
        
        reverse = (order == Qt.SortOrder.DescendingOrder)
        
        key_func = None
        if column == self.COL_ALIAS:
            key_func = lambda x: x.alias
        elif column == self.COL_SALARY:
            key_func = lambda x: x.salary_sort
        elif column == self.COL_DURATION:
            key_func = lambda x: x.duration_left_sort
        elif column == self.COL_COMPLIANCE:
            key_func = lambda x: x.compliance_sort
        elif column == self.COL_DATES:
            key_func = lambda x: x.start_week_sort
        elif column == self.COL_USAGE:
            key_func = lambda x: x.usage_sort
        elif column == self.COL_ORIENTATIONS:
            key_func = lambda x: x.allowed_orientations
        elif column == self.COL_CONCEPTS:
            key_func = lambda x: x.allowed_concepts
        elif column == self.COL_DYN_DISP:
            key_func = lambda x: x.limits_dynamic_disposition
            
        if key_func:
            self._data.sort(key=key_func, reverse=reverse)
            
        self.layoutChanged.emit()