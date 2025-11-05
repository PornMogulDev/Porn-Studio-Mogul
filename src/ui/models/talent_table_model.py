from typing import List, Union, Dict
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt

from data.game_state import Talent
from database.db_models import TalentDB
from utils.formatters import format_orientation, format_dick_size, get_fuzzed_skill_range, format_skill_range
from ui.models.talent_view_model import TalentViewModel

class TalentTableModel(QAbstractTableModel):
    def __init__(self, settings_manager, boob_cup_order: List[str], mode: str = 'default', parent=None):
        super().__init__(parent)
        # Store raw data instead of pre-calculated ViewModels
        self.raw_data: List[Union[TalentDB, dict]] = []
        # Cache for lazy-loaded ViewModels (row_index -> ViewModel)
        self._viewmodel_cache: Dict[int, TalentViewModel] = {}
        self.settings_manager = settings_manager
        self.mode = mode
        self._cup_map = {cup: i for i, cup in enumerate(boob_cup_order)} if boob_cup_order else {}
        self.headers = ["Alias", "Age", "Gender", "Orientation", "Ethnicity", "Dick Size", "Cup Size", "Perf.", "Act.", "Dom", "Sub", "Stam.", "Pop."]
    
        if self.mode == 'casting':
            self.headers.append("Demand")

    def data(self, index: QModelIndex, role: int):
        if not index.isValid() or not (0 <= index.row() < len(self.raw_data)):
            return None
        
        row = index.row()
        col = index.column()
        
        # Lazy-load the ViewModel for this row
        item = self._get_or_create_viewmodel(row)
        if item is None:
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0: return item.alias
            if col == 1: return item.age
            if col == 2: return item.gender
            if col == 3: return item.orientation
            if col == 4: return item.ethnicity
            if col == 5: return item.dick_size
            if col == 6: return item.cup_size
            if col == 7: return item.performance
            if col == 8: return item.acting
            if col == 9: return item.dom
            if col == 10: return item.sub
            if col == 11: return item.stamina
            if col == 12: return item.popularity
            if col == 13 and self.mode == 'casting': return item.demand
        
        elif role == Qt.ItemDataRole.UserRole:
            # The ViewModel stores the full Talent dataclass for easy access
            # by other parts of the UI (like opening a profile).
            return item.talent_obj
 
        return None
        
    def rowCount(self, parent: QModelIndex = QModelIndex()):
        return len(self.raw_data)

    def columnCount(self, parent: QModelIndex = QModelIndex()):
        return len(self.headers)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return None

    def update_data(self, new_data: List[Union[TalentDB, dict]]):
        """
        Stores raw data and clears the ViewModel cache.
        ViewModels are now created lazily on-demand when rows are accessed.
        """
        self.beginResetModel()
        self.raw_data = new_data
        # Clear the cache when new data arrives
        self._viewmodel_cache.clear()
        self.endResetModel()
    
    def _get_or_create_viewmodel(self, row: int) -> Union[TalentViewModel, None]:
        """
        Lazily creates and caches a ViewModel for the given row.
        This is called on-demand when data() is invoked for visible rows.
        """
        if row in self._viewmodel_cache:
            return self._viewmodel_cache[row]
        
        if row >= len(self.raw_data):
            return None
        
        item = self.raw_data[row]
        unit_system = self.settings_manager.get_setting("unit_system", "imperial")
        
        if self.mode == 'casting':
            talent_obj = item['talent']
            demand = item['demand']
        else:
            talent_obj = item
            demand = 0

        # --- Calculate all fuzzed skills and their sort/display values ONCE ---
        perf_fuzzed = get_fuzzed_skill_range(talent_obj.performance, talent_obj.experience, talent_obj.id)
        act_fuzzed = get_fuzzed_skill_range(talent_obj.acting, talent_obj.experience, talent_obj.id)
        stam_fuzzed = get_fuzzed_skill_range(talent_obj.stamina, talent_obj.experience, talent_obj.id)
        dom_fuzzed = get_fuzzed_skill_range(talent_obj.dom_skill, talent_obj.experience, talent_obj.id)
        sub_fuzzed = get_fuzzed_skill_range(talent_obj.sub_skill, talent_obj.experience, talent_obj.id)

        perf_sort = perf_fuzzed if isinstance(perf_fuzzed, int) else perf_fuzzed[0]
        act_sort = act_fuzzed if isinstance(act_fuzzed, int) else act_fuzzed[0]
        stam_sort = stam_fuzzed if isinstance(stam_fuzzed, int) else stam_fuzzed[0]
        dom_sort = dom_fuzzed if isinstance(dom_fuzzed, int) else dom_fuzzed[0]
        sub_sort = sub_fuzzed if isinstance(sub_fuzzed, int) else sub_fuzzed[0]

        # --- Calculate popularity ---
        if hasattr(talent_obj, 'popularity_scores'): # TalentDB object
            popularity = round(sum(p.score for p in talent_obj.popularity_scores) if talent_obj.popularity_scores else 0)
        elif hasattr(talent_obj, 'popularity'): # Talent dataclass
            popularity = round(sum(talent_obj.popularity.values()))
        else:
            popularity = 0

        # --- Create the ViewModel with all pre-calculated values ---
        vm = TalentViewModel(
            talent_obj=talent_obj.to_dataclass(Talent) if hasattr(talent_obj, 'to_dataclass') else talent_obj,
            
            # Display Strings
            alias=talent_obj.alias,
            age=str(talent_obj.age),
            gender=talent_obj.gender,
            orientation=format_orientation(talent_obj.orientation_score, talent_obj.gender),
            ethnicity=talent_obj.ethnicity,
            dick_size=format_dick_size(talent_obj.dick_size, unit_system) if talent_obj.gender == "Male" and talent_obj.dick_size is not None else "N/A",
            cup_size=talent_obj.boob_cup if talent_obj.gender == "Female" else "N/A",
            performance=format_skill_range(perf_fuzzed),
            acting=format_skill_range(act_fuzzed),
            dom=format_skill_range(dom_fuzzed),
            sub=format_skill_range(sub_fuzzed),
            stamina=format_skill_range(stam_fuzzed),
            popularity=str(popularity),
            demand=f"${demand:,}" if self.mode == 'casting' else "",

            # Sort Keys
            _age_sort=talent_obj.age,
            _orientation_sort=talent_obj.orientation_score,
            _dick_size_sort=talent_obj.dick_size if talent_obj.dick_size is not None else -1,
            _cup_size_sort=self._cup_map.get(talent_obj.boob_cup, -1),
            _performance_sort=perf_sort,
            _acting_sort=act_sort,
            _dom_sort=dom_sort,
            _sub_sort=sub_sort,
            _stamina_sort=stam_sort,
            _popularity_sort=popularity,
            _demand_sort=demand
        )
        
        # Cache the ViewModel for this row
        self._viewmodel_cache[row] = vm
        return vm

    def sort(self, column: int, order: Qt.SortOrder):
        """Sorts the raw data by creating ViewModels on-demand for sorting."""
        self.layoutAboutToBeChanged.emit()
        
        reverse = (order == Qt.SortOrder.DescendingOrder)

        # Define sort key extractors that work on raw data
        # We need to create ViewModels for all items during sort
        def get_sort_key(row_index: int):
            vm = self._get_or_create_viewmodel(row_index)
            if vm is None:
                return 0  # Fallback value
            
            if column == 0: return vm.alias.lower()
            elif column == 1: return vm._age_sort
            elif column == 2: return vm.gender
            elif column == 3: return vm._orientation_sort
            elif column == 4: return vm.ethnicity
            elif column == 5: return vm._dick_size_sort
            elif column == 6: return vm._cup_size_sort
            elif column == 7: return vm._performance_sort
            elif column == 8: return vm._acting_sort
            elif column == 9: return vm._dom_sort
            elif column == 10: return vm._sub_sort
            elif column == 11: return vm._stamina_sort
            elif column == 12: return vm._popularity_sort
            elif column == 13 and self.mode == 'casting': return vm._demand_sort
            return 0
        
        # Create index list and sort by indices
        indices = list(range(len(self.raw_data)))
        indices.sort(key=get_sort_key, reverse=reverse)
        
        # Reorder raw_data and update cache indices
        sorted_raw_data = [self.raw_data[i] for i in indices]
        
        # Rebuild cache with new indices
        old_cache = self._viewmodel_cache
        self._viewmodel_cache = {}
        for new_idx, old_idx in enumerate(indices):
            if old_idx in old_cache:
                self._viewmodel_cache[new_idx] = old_cache[old_idx]
        
        self.raw_data = sorted_raw_data
        self.layoutChanged.emit()