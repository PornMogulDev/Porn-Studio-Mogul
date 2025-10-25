from typing import Tuple, Optional
from PyQt6.QtGui import QColor

from data.game_state import Talent

#Helper dictionary to map chemistry scores to display text and color
CHEMISTRY_MAP = {
2: ("Great", QColor("darkGreen")),
1: ("Good", QColor("green")),
0: ("Neutral", QColor("gray")),
-1: ("Bad", QColor("#FF8C00")), # Dark Orange
-2: ("Terrible", QColor("red")),
}

def format_orientation(score: int, gender: str) -> str:
    """Converts an orientation score (-100 to 100) into a detailed display string."""
    if -100 <= score <= -81: return "Straight"
    if -80 <= score <= -30: return "Mostly Straight"
    if -29 <= score <= 29: return "Bisexual"
    if 30 <= score <= 79:
        return "Mostly Lesbian" if gender == "Female" else "Mostly Gay"
    if 80 <= score <= 100:
        return "Lesbian" if gender == "Female" else "Gay"
    return "Unknown"
def format_dick_size(inches: float, unit_system: str) -> str:
    """Formats a dick size in inches to the desired unit system's string representation."""
    if unit_system == 'metric':
        cm_value = inches * 2.54
        return f"{cm_value:.1f} cm"
    else:  # imperial
        return f'{inches}"'

def format_physical_attribute(talent: Talent, unit_system: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Determines the primary physical attribute and formats it for display.
     
     Returns:
        A tuple of (attribute_name, formatted_value). E.g., ("Dick", '7.1"').
        Returns (None, None) if no relevant attribute is present.
    """
    if talent.gender == "Female" and talent.boob_cup:
        return "Cup Size", f"{talent.boob_cup}"
    elif talent.gender == "Male" and talent.dick_size is not None:
        return "Dick Size", format_dick_size(talent.dick_size, unit_system)
    return None, None