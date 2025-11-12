from dataclasses import dataclass
from typing import Union

from data.game_state import Talent
from database.db_models import TalentDB

@dataclass
class TalentViewModel:
    """
    A data container holding pre-formatted and pre-calculated values for the talent table.

    This object acts as a bridge between the raw data models (TalentDB/Talent) and the
    QTableView. It performs all necessary calculations and formatting once upon creation,
    making the table model's `data()` and `sort()` methods extremely fast and simple.
    """
    # The original data object, preserved for UserRole lookups (e.g., for opening a profile).
    talent_obj: Union[Talent, TalentDB]

    # --- Pre-formatted Display Strings (for DisplayRole) ---
    alias: str
    age: str
    gender: str
    orientation: str
    ethnicity: str
    nationality: str
    location: str
    dick_size: str
    cup_size: str
    performance: str
    acting: str
    dom: str
    sub: str
    stamina: str
    popularity: str
    demand: str  # Populated only in 'casting' mode, otherwise an empty string.

    # --- Pre-calculated Sort Keys (for efficient sorting) ---
    # These hold the raw, sortable values corresponding to the display strings above.
    _age_sort: int
    _orientation_sort: int
    _nationality_sort: str
    _location_sort: str
    _dick_size_sort: float
    _cup_size_sort: int
    _performance_sort: int
    _acting_sort: int
    _dom_sort: int
    _sub_sort: int
    _stamina_sort: int
    _popularity_sort: int
    _demand_sort: int  # Populated only in 'casting' mode, otherwise 0.