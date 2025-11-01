from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex, QSortFilterProxyModel
from typing import List
from data.game_state import Scene

class SceneSortFilterProxyModel(QSortFilterProxyModel):
    """
    Custom proxy model to handle sorting specific columns numerically
    instead of lexicographically.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._date_col_idx = -1
        self._revenue_col_idx = -1
    
    def setSourceModel(self, sourceModel: QAbstractTableModel):
        """Cache column indexes when the source model is set."""
        super().setSourceModel(sourceModel)
        if sourceModel:
            try:
                self._date_col_idx = sourceModel._headers.index("Date")
                self._revenue_col_idx = sourceModel._headers.index("Revenue")
            except (AttributeError, ValueError):
                self._date_col_idx = -1
                self._revenue_col_idx = -1

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        source_model = self.sourceModel()
        col = left.column()

        # Get the underlying Scene objects for comparison
        left_scene = source_model.data(left, Qt.ItemDataRole.UserRole)
        right_scene = source_model.data(right, Qt.ItemDataRole.UserRole)

        if not left_scene or not right_scene:
            return super().lessThan(left, right)

        # --- Check for Date column ---
        if col == self._date_col_idx:
            left_date_val = left_scene.scheduled_year * 52 + left_scene.scheduled_week
            right_date_val = right_scene.scheduled_year * 52 + right_scene.scheduled_week
            return left_date_val < right_date_val
        
        # --- NEW: Check for Revenue column ---
        elif col == self._revenue_col_idx:
            # Treat N/A (non-released scenes) as 0 for sorting purposes
            left_revenue = left_scene.revenue if left_scene.status == 'released' else 0
            right_revenue = right_scene.revenue if right_scene.status == 'released' else 0
            return left_revenue < right_revenue

        # --- Fallback to default behavior for all other columns ---
        return super().lessThan(left, right)


class SceneTableModel(QAbstractTableModel):
    def __init__(self, scenes: List[Scene] = None, controller=None, parent=None):
        super().__init__(parent)
        self._scenes = scenes or []
        self._headers = ["Title", "Status", "Date", "Revenue", "Cast"]
        self.controller = controller

    def rowCount(self, parent=QModelIndex()):
        return len(self._scenes)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not self.controller: return None
        scene = self._scenes[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0: return scene.title
            elif col == 1: return scene.display_status
            elif col == 2:
                if scene.scheduled_year == -1 or scene.scheduled_week == -1: return "Unscheduled"
                return f"W{scene.scheduled_week}, {scene.scheduled_year}"
            elif col == 3:
                if scene.status == 'released': return f"${scene.revenue:,}"
                return "N/A"
            elif col == 4:
                if not scene.final_cast:
                    return f"({len(scene.virtual_performers)} roles uncast)"
                
                talent_aliases = []
                for talent_id in scene.final_cast.values():
                    talent = self.controller.query_service.get_talent_by_id(talent_id)
                    talent_aliases.append(talent.alias if talent else f"ID {talent_id}?")
                return ", ".join(talent_aliases)
        
        if role == Qt.ItemDataRole.UserRole:
            return scene
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self._headers[section]
        return None

    def setScenes(self, scenes: List[Scene]):
        self.beginResetModel()
        self._scenes = scenes
        self.endResetModel()