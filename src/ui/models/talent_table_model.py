from typing import List, Union, Dict, Optional
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt

from core.interfaces import IGameController
from data.game_state import Talent
from utils.formatters import format_orientation, format_dick_size, format_skill_range
from ui.models.talent_view_model import TalentViewModel
from ui.presenters.talent_filter_cache import TalentFilterCache, CastingTalentCache

class TalentTableModel(QAbstractTableModel):
    def __init__(self, settings_manager, controller: IGameController, cup_size_order: List[str], parent=None):
        super().__init__(parent)
        self.raw_data: List[Union[TalentFilterCache, CastingTalentCache]] = []
        self._viewmodel_cache: Dict[int, TalentViewModel] = {}
        self.settings_manager = settings_manager
        self.controller = controller
        
        # --- Casting Context ---
        self._scene_id: Optional[int] = None
        self._vp_id: Optional[int] = None

        self._cup_map = {cup: i for i, cup in enumerate(cup_size_order)} if cup_size_order else {}
        self.headers = ["Alias", "Age", "Gender", "Orientation", "Ethnicity", "Nationality", "Location", "Dick Size", "Cup Size", "Perf.", "Act.", "Dom", "Sub", "Stam.", "Pop.", "Demand"]
    
    def set_casting_context(self, scene_id: Optional[int], vp_id: Optional[int]):
        """Sets the current role context for demand calculation."""
        self._scene_id = scene_id
        self._vp_id = vp_id
        self.refresh() # Clear cache and redraw

    def data(self, index: QModelIndex, role: int):
        if not index.isValid() or not (0 <= index.row() < len(self.raw_data)): return None
        
        row, col = index.row(), index.column()
        item = self._get_or_create_viewmodel(row)
        if item is None: return None

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0: return item.alias
            if col == 1: return item.age
            if col == 2: return item.gender
            if col == 3: return item.orientation
            if col == 4: return item.ethnicity
            if col == 5: return item.nationality
            if col == 6: return item.location
            if col == 7: return item.dick_size
            if col == 8: return item.cup_size
            if col == 9: return item.performance
            if col == 10: return item.acting
            if col == 11: return item.dom
            if col == 12: return item.sub
            if col == 13: return item.stamina
            if col == 14: return item.popularity
            if col == 15: return item.demand
        
        elif role == Qt.ItemDataRole.UserRole: return item.talent_obj
        return None
        
    def rowCount(self, parent: QModelIndex = QModelIndex()): return len(self.raw_data)
    def columnCount(self, parent: QModelIndex = QModelIndex()): return len(self.headers)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return None

    def update_data(self, new_data: List[Union[TalentFilterCache, CastingTalentCache]]):
        self.beginResetModel(); self.raw_data = new_data; self._viewmodel_cache.clear(); self.endResetModel()

    def refresh(self):
        self.beginResetModel(); self._viewmodel_cache.clear(); self.endResetModel()
    
    def _get_or_create_viewmodel(self, row: int) -> Optional[TalentViewModel]:
        if row in self._viewmodel_cache: return self._viewmodel_cache[row]
        if row >= len(self.raw_data): return None
        
        cache_item = self.raw_data[row]
        talent_obj = cache_item.talent_db
        unit_system = self.settings_manager.get_setting("unit_system", "imperial")
        
        # --- Lazy Load Demand Calculation ---
        demand_val = None
        if self._scene_id is not None and self._vp_id is not None:
            _, _, demand_val = self.controller.calculate_total_demand(talent_obj.id, self._scene_id, self._vp_id)
        
        perf_range, act_range, stam_range, dom_range, sub_range = cache_item.perf_range, cache_item.act_range, cache_item.stam_range, cache_item.dom_range, cache_item.sub_range
        
        vm = TalentViewModel(
            talent_obj=talent_obj.to_dataclass(Talent),
            alias=talent_obj.alias, age=str(talent_obj.age), gender=talent_obj.gender,
            orientation=format_orientation(talent_obj.orientation_score, talent_obj.gender),
            ethnicity=talent_obj.ethnicity, nationality=talent_obj.nationality, location=talent_obj.base_location,
            dick_size=format_dick_size(talent_obj.dick_size, unit_system) if talent_obj.gender == "Male" and talent_obj.dick_size is not None else "N/A",
            cup_size=talent_obj.cup_size if talent_obj.gender == "Female" else "N/A",
            performance=format_skill_range(perf_range), acting=format_skill_range(act_range),
            dom=format_skill_range(dom_range), sub=format_skill_range(sub_range),
            stamina=format_skill_range(stam_range), popularity=str(cache_item.popularity),
            demand=f"${demand_val:,}" if demand_val is not None else "N/A",
            _age_sort=talent_obj.age, _orientation_sort=talent_obj.orientation_score,
            _nationality_sort=talent_obj.nationality or "", _location_sort=talent_obj.base_location or "",
            _dick_size_sort=talent_obj.dick_size if talent_obj.dick_size is not None else -1,
            _cup_size_sort=self._cup_map.get(talent_obj.cup_size, -1),
            _performance_sort=perf_range[0] if isinstance(perf_range, tuple) else perf_range,
            _acting_sort=act_range[0] if isinstance(act_range, tuple) else act_range,
            _dom_sort=dom_range[0] if isinstance(dom_range, tuple) else dom_range,
            _sub_sort=sub_range[0] if isinstance(sub_range, tuple) else sub_range,
            _stamina_sort=stam_range[0] if isinstance(stam_range, tuple) else stam_range,
            _popularity_sort=cache_item.popularity, _demand_sort=demand_val if demand_val is not None else -1
        )
        self._viewmodel_cache[row] = vm
        return vm

    def sort(self, column: int, order: Qt.SortOrder):
        # --- Pre-calculation for demand sorting ---
        if self.headers[column] == "Demand" and self._scene_id is not None:
            for i in range(len(self.raw_data)): self._get_or_create_viewmodel(i)
        
        self.layoutAboutToBeChanged.emit()
        reverse = (order == Qt.SortOrder.DescendingOrder)

        def get_sort_key(row_index: int):
            vm = self._get_or_create_viewmodel(row_index)
            if vm is None: return 0
            if column == 0: return vm.alias.lower()
            if column == 1: return vm._age_sort
            if column == 2: return vm.gender
            if column == 3: return vm._orientation_sort
            if column == 4: return vm.ethnicity
            if column == 5: return vm._nationality_sort.lower()
            if column == 6: return vm._location_sort.lower()
            if column == 7: return vm._dick_size_sort
            if column == 8: return vm._cup_size_sort
            if column == 9: return vm._performance_sort
            if column == 10: return vm._acting_sort
            if column == 11: return vm._dom_sort
            if column == 12: return vm._sub_sort
            if column == 13: return vm._stamina_sort
            if column == 14: return vm._popularity_sort
            if column == 15: return vm._demand_sort
            return 0
        
        indices = sorted(range(len(self.raw_data)), key=get_sort_key, reverse=reverse)
        sorted_raw_data = [self.raw_data[i] for i in indices]
        
        old_cache = self._viewmodel_cache.copy(); self._viewmodel_cache.clear()
        for new_idx, old_idx in enumerate(indices):
            if old_idx in old_cache: self._viewmodel_cache[new_idx] = old_cache[old_idx]
        
        self.raw_data = sorted_raw_data
        self.layoutChanged.emit()