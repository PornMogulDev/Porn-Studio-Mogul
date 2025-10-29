from typing import List, Optional, Union, Tuple
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt

from data.game_state import Talent
from database.db_models import TalentDB
from utils.formatters import format_orientation, format_dick_size, get_fuzzed_skill_range, format_skill_range

class TalentTableModel(QAbstractTableModel):
    def __init__(self, settings_manager, boob_cup_order: List[str], mode: str = 'default', parent=None):
        super().__init__(parent)
        self.display_data = [] # Will store Talent objects or dicts {'talent': Talent, 'demand': int}
        self.settings_manager = settings_manager
        self.mode = mode
        self._cup_map = {cup: i for i, cup in enumerate(boob_cup_order)} if boob_cup_order else {}
        self.headers = ["Alias", "Age", "Gender", "Orientation", "Ethnicity", "Dick Size", "Cup Size", "Perf.", "Act.", "Stam.", "Pop."]
    
        if self.mode == 'casting':
            self.headers.append("Demand")

    def data(self, index: QModelIndex, role: int):
        if not index.isValid(): return None
        item = self.display_data[index.row()]
        talent_db = item['talent'] if self.mode == 'casting' else item
        col = index.column()

        unit_system = self.settings_manager.get_setting("unit_system") if self.settings_manager else "metric"

        if role == Qt.ItemDataRole.DisplayRole:
              # Common columns
            if col == 0: return talent_db.alias # Assuming 'talent_db' can be a dataclass
            elif col == 1: return talent_db.age
            elif col == 2: return talent_db.gender
            elif col == 3: return format_orientation(talent_db.orientation_score, talent_db.gender)
            elif col == 4: return talent_db.ethnicity
            elif col == 5:
                  if talent_db.gender == "Male" and talent_db.dick_size is not None: return format_dick_size(talent_db.dick_size, unit_system)
                  return "N/A"
            elif col == 6: return talent_db.boob_cup if talent_db.gender == "Female" else "N/A"
            elif col == 7:  # Performance
                return format_skill_range(get_fuzzed_skill_range(talent_db.performance, talent_db.experience, talent_db.id))
            elif col == 8:  # Acting
                return format_skill_range(get_fuzzed_skill_range(talent_db.acting, talent_db.experience, talent_db.id))
            elif col == 9:  # Stamina
                return format_skill_range(get_fuzzed_skill_range(talent_db.stamina, talent_db.experience, talent_db.id))
            elif col == 10:
                # Handle both TalentDB (has .popularity_scores) and Talent dataclass (has .popularity)
                if hasattr(talent_db, 'popularity_scores'):
                    pop = sum(p.score for p in talent_db.popularity_scores) if talent_db.popularity_scores else 0.0
                elif hasattr(talent_db, 'popularity'):
                    pop = sum(talent_db.popularity.values())
                else:
                    pop = 0.0
                return str(round(pop))
            # Casting-specific column
            elif col == 11 and self.mode == 'casting':
                return f"${item['demand']:,}"
            elif col == 10:
                # Handle both TalentDB (has .popularity_scores) and Talent dataclass (has .popularity)
                if hasattr(talent_db, 'popularity_scores'):
                    pop = sum(p.score for p in talent_db.popularity_scores)
                elif hasattr(talent_db, 'popularity'):
                    pop = sum(talent_db.popularity.values())
                else:
                    pop = 0.0
                return f"{pop:.2f}"
            # Casting-specific column
            elif col == 11 and self.mode == 'casting':
                return f"${item['demand']:,}"

        elif role == Qt.ItemDataRole.UserRole:
            # If it's a DB model, convert it. If it's already a dataclass, return it as is.
            if hasattr(talent_db, 'to_dataclass'):
                return talent_db.to_dataclass(Talent)
            return talent_db
 
        return None
        
    def rowCount(self, parent: QModelIndex = QModelIndex()): return len(self.display_data)
    def columnCount(self, parent: QModelIndex = QModelIndex()): return len(self.headers)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return None

    def update_data(self, new_data: List):
        """Accepts a list of Talent objects (default) or a list of dicts (casting)."""
        self.beginResetModel()
        self.display_data = new_data
        self.endResetModel()

    def sort(self, column: int, order: Qt.SortOrder):
        """Sorts the model by the given column and order."""
        self.layoutAboutToBeChanged.emit()
        
        reverse = (order == Qt.SortOrder.DescendingOrder)

        def get_skill_sort_value(skill_val: float, exp: float) -> int:
            """Helper to get the sort value from a fuzzed skill (min of range or accurate value)."""
            fuzzed = get_fuzzed_skill_range(skill_val, exp)
            if isinstance(fuzzed, tuple):
                return fuzzed[0] # Sort by the minimum of the range
            return fuzzed

        def get_sort_key(item):
            talent_db = item['talent'] if self.mode == 'casting' else item

            def get_skill_sort_value_with_id(skill_val: float, exp: float, talent_id: int) -> int:
                fuzzed = get_fuzzed_skill_range(skill_val, exp, talent_id)
                if isinstance(fuzzed, tuple):
                    return fuzzed[0]
                return fuzzed

            if column == 0:  # Alias
                return talent_db.alias.lower()
            if column == 1:  # Age
                return talent_db.age
            if column == 2:  # Gender
                return talent_db.gender
            if column == 3:  # Orientation
                return talent_db.orientation_score
            if column == 4:  # Ethnicity
                return talent_db.ethnicity
            if column == 5:  # Dick Size
                return talent_db.dick_size if talent_db.dick_size is not None else -1
            if column == 6:  # Cup Size
                return self._cup_map.get(talent_db.boob_cup, -1)
            if column == 7:  # Performance
                return get_skill_sort_value_with_id(talent_db.performance, talent_db.experience, talent_db.id)
            if column == 8:  # Acting
                return get_skill_sort_value_with_id(talent_db.acting, talent_db.experience, talent_db.id)
            if column == 9:  # Stamina
                return get_skill_sort_value_with_id(talent_db.stamina, talent_db.experience, talent_db.id)
            if column == 10: # Popularity
                if hasattr(talent_db, 'popularity_scores'):
                    return round(sum(p.score for p in talent_db.popularity_scores) if talent_db.popularity_scores else 0)
                elif hasattr(talent_db, 'popularity'):
                    return round(sum(talent_db.popularity.values()))
                return 0
            if column == 11 and self.mode == 'casting': # Demand
                return item['demand']
            return 0

        self.display_data.sort(key=get_sort_key, reverse=reverse)
        
        self.layoutChanged.emit()