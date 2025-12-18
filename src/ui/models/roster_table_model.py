from typing import List, Any
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PyQt6.QtGui import QColor

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
    COL_START_DATE = 4
    COL_END_DATE = 5
    COL_USAGE = 6
    COL_ORIENTATIONS = 7
    COL_CONCEPTS = 8
    COL_DYN_DISP = 9
    
    HEADERS = [
        "Alias", 
        "Weekly Salary", 
        "Remaining", 
        "Compliance", 
        "Start Date",
        "End Date", 
        "Scenes/Month",
        "Orientations", 
        "Concepts", 
        "Dyn / Disp"
    ]

    def __init__(self, theme_manager, settings_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.settings_manager = settings_manager
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
            elif col == self.COL_START_DATE:
                return row_item.start_date_display
            elif col == self.COL_END_DATE:
                return row_item.end_date_display
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
            if col == self.COL_COMPLIANCE:
                val = row_item.compliance_sort
                current_theme_name = self.settings_manager.get_setting("theme", "light")
                theme = self.theme_manager.get_theme(current_theme_name)
                
                if val >= 70:
                    return QColor(theme.color_good)
                elif val >= 35:
                    return QColor(theme.color_warning)
                else:
                    return QColor(theme.color_bad)
            
        # Tooltip Role: Show full content for potentially truncated columns
        elif role == Qt.ItemDataRole.ToolTipRole:
            if col == self.COL_ORIENTATIONS:
                return row_item.allowed_orientations
            elif col == self.COL_CONCEPTS:
                return row_item.allowed_concepts
            # For other columns, default behavior is usually fine, or return None

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
        elif column == self.COL_START_DATE:
            key_func = lambda x: x.start_week_sort
        elif column == self.COL_END_DATE:
            key_func = lambda x: x.end_week_sort    
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