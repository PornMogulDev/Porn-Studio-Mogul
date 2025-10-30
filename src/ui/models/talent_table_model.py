from typing import List, Union
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt

from data.game_state import Talent
from database.db_models import TalentDB
from utils.formatters import format_orientation, format_dick_size, get_fuzzed_skill_range, format_skill_range
from ui.models.talent_view_model import TalentViewModel

class TalentTableModel(QAbstractTableModel):
    def __init__(self, settings_manager, boob_cup_order: List[str], mode: str = 'default', parent=None):
        super().__init__(parent)
        self.display_data: List[TalentViewModel] = []
        self.settings_manager = settings_manager
        self.mode = mode
        self._cup_map = {cup: i for i, cup in enumerate(boob_cup_order)} if boob_cup_order else {}
        self.headers = ["Alias", "Age", "Gender", "Orientation", "Ethnicity", "Dick Size", "Cup Size", "Perf.", "Act.", "Dom", "Sub", "Stam.", "Pop."]
    
        if self.mode == 'casting':
            self.headers.append("Demand")

    def data(self, index: QModelIndex, role: int):
        if not index.isValid() or not (0 <= index.row() < len(self.display_data)):
            return None
        
        item = self.display_data[index.row()]
        col = index.column()

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
        return len(self.display_data)

    def columnCount(self, parent: QModelIndex = QModelIndex()):
        return len(self.headers)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return None

    def update_data(self, new_data: List[Union[TalentDB, dict]]):
        """
        Accepts raw data, transforms it into ViewModels, and resets the model.
        This is where all formatting and calculation now occurs.
        """
        self.beginResetModel()

        view_models = []
        unit_system = self.settings_manager.get_setting("unit_system", "imperial")

        for item in new_data:
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
            view_models.append(vm)

        self.display_data = view_models
        self.endResetModel()

    def sort(self, column: int, order: Qt.SortOrder):
        """Sorts the model using the pre-calculated sort keys in the ViewModel."""
        self.layoutAboutToBeChanged.emit()
        
        reverse = (order == Qt.SortOrder.DescendingOrder)

        sorter = None
        if column == 0: sorter = lambda vm: vm.alias.lower()
        elif column == 1: sorter = lambda vm: vm._age_sort
        elif column == 2: sorter = lambda vm: vm.gender
        elif column == 3: sorter = lambda vm: vm._orientation_sort
        elif column == 4: sorter = lambda vm: vm.ethnicity
        elif column == 5: sorter = lambda vm: vm._dick_size_sort
        elif column == 6: sorter = lambda vm: vm._cup_size_sort
        elif column == 7: sorter = lambda vm: vm._performance_sort
        elif column == 8: sorter = lambda vm: vm._acting_sort
        elif column == 9: sorter = lambda vm: vm._dom_sort
        elif column == 10: sorter = lambda vm: vm._sub_sort
        elif column == 11: sorter = lambda vm: vm._stamina_sort
        elif column == 12: sorter = lambda vm: vm._popularity_sort
        elif column == 13 and self.mode == 'casting': sorter = lambda vm: vm._demand_sort
        
        if sorter:
            self.display_data.sort(key=sorter, reverse=reverse)
        
        self.layoutChanged.emit()