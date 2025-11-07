from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex, QSortFilterProxyModel
from typing import List
from data.game_state import Scene
from ui.view_models import SceneViewModel

class SceneSortFilterProxyModel(QSortFilterProxyModel):
    """
    Custom proxy model to handle sorting specific columns numerically
    instead of lexicographically. It operates on the raw Scene object
    stored in the UserRole of the source model.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._date_col_idx = -1
        self._revenue_col_idx = -1
    
    def setSourceModel(self, sourceModel: QAbstractTableModel):
        """Cache column indexes when the source model is set."""
        super().setSourceModel(sourceModel)
        if sourceModel and hasattr(sourceModel, '_headers'):
            try:
                # Assuming the headers are consistent in SceneTableModel
                headers = sourceModel._headers
                self._date_col_idx = headers.index("Date")
                self._revenue_col_idx = headers.index("Revenue")
            except (AttributeError, ValueError):
                self._date_col_idx = -1
                self._revenue_col_idx = -1

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        source_model = self.sourceModel()
        col = left.column()

        # Get the underlying raw Scene objects for comparison
        left_scene: Scene = source_model.data(left, Qt.ItemDataRole.UserRole)
        right_scene: Scene = source_model.data(right, Qt.ItemDataRole.UserRole)

        if not left_scene or not right_scene:
            return super().lessThan(left, right)

        # --- Check for Date column ---
        if col == self._date_col_idx:
            left_date_val = left_scene.scheduled_year * 52 + left_scene.scheduled_week
            right_date_val = right_scene.scheduled_year * 52 + right_scene.scheduled_week
            return left_date_val < right_date_val
        
        # --- Check for Revenue column ---
        elif col == self._revenue_col_idx:
            # Treat N/A (non-released scenes) as 0 for sorting purposes
            left_revenue = left_scene.revenue if left_scene.status == 'released' else 0
            right_revenue = right_scene.revenue if right_scene.status == 'released' else 0
            return left_revenue < right_revenue

        # --- Fallback to default behavior for all other columns ---
        return super().lessThan(left, right)


class SceneTableModel(QAbstractTableModel):
    """
    A "dumb" table model that displays pre-processed SceneViewModel data.
    It holds both the view models for display and the raw data for sorting/filtering.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scenes_vm: List[SceneViewModel] = []
        self._raw_scenes: List[Scene] = []
        self._headers = ["Title", "Status", "Date", "Revenue", "Cast"]

    def rowCount(self, parent=QModelIndex()):
        return len(self._scenes_vm)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        
        row = index.row()
        col = index.column()

        if row >= len(self._scenes_vm):
            return None

        vm = self._scenes_vm[row]

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0: return vm.title
            elif col == 1: return vm.display_status
            elif col == 2: return vm.date_str
            elif col == 3: return vm.revenue_str
            elif col == 4: return vm.cast_str
        
        # The UserRole provides the raw Scene object, which is used by the
        # SceneSortFilterProxyModel for accurate numerical sorting.
        if role == Qt.ItemDataRole.UserRole:
            if row < len(self._raw_scenes):
                return self._raw_scenes[row]
            return None
            
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self._headers[section]
        return None

    def update_data(self, scenes_vm: List[SceneViewModel], raw_scenes: List[Scene]):
        """
        Receives new data from the presenter and refreshes the model.
        """
        self.beginResetModel()
        self._scenes_vm = scenes_vm
        self._raw_scenes = raw_scenes
        self.endResetModel()

    def get_view_model_by_row(self, row: int) -> SceneViewModel | None:
        """Allows external components like the view to get the ViewModel for a given row."""
        if 0 <= row < len(self._scenes_vm):
            return self._scenes_vm[row]
        return None