from dataclasses import dataclass
from typing import Any

@dataclass
class RosterViewModel:
    """
    Represents a single row in the Roster View table.
    Holds both display strings and raw values for sorting.
    """
    talent_id: int
    talent_obj: Any  # The Talent object (for Entity Card UserRole)
    
    # -- Columns --
    alias: str
    
    salary_display: str
    salary_sort: int
    
    duration_left_display: str
    duration_left_sort: int # Weeks remaining
    
    compliance_display: str
    compliance_sort: int # 0-100
    
    dates_display: str # "Start - End"
    start_week_sort: int # For sorting by date
    
    allowed_orientations: str
    allowed_concepts: str
    
    limits_dynamic_disposition: str # "Dom / Switch"
    
    usage_display: str # "2/4"
    usage_sort: float # ratio or remaining count