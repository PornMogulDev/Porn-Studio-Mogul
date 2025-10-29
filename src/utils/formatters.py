from typing import Tuple, Optional
from PyQt6.QtGui import QColor

from ui.theme_manager import Theme
from data.game_state import Talent

def get_chemistry_map(theme: Theme) -> dict:
    """
    Generates a chemistry map with colors from the current theme.
    This replaces the static CHEMISTRY_MAP dictionary.
    """
    return {
        2: ("Great", QColor(theme.color_good)),
        1: ("Good", QColor(theme.color_good)),
        0: ("Neutral", QColor(theme.color_neutral)),
        -1: ("Bad", QColor(theme.color_warning)),
        -2: ("Terrible", QColor(theme.color_bad)),
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

def fuzz_skill_value(skill_value: float, experience: float) -> str:
    """
    Returns a fuzzed string representation of a skill based on player experience with the talent.
    """
    if experience < 5:
        return "???"
    elif experience < 20:
        # Wide range, rounded to nearest 5
        base = round(skill_value / 5) * 5
        return f"{max(0, base - 5)} - {min(100, base + 5)}"
    elif experience < 40:
        # Tilde, rounded to nearest integer
        return f"~{round(skill_value)}"
    elif experience < 65:
        # Show integer value, no decimals
        return str(round(skill_value))
    elif experience < 85:
        # Show one decimal place
        return f"{skill_value:.1f}"
    else: # Max experience
        # Show the "true" value
        return f"{skill_value:.2f}"
    
def format_fatigue(fatigue_level: int) -> str:
    """Converts a numeric fatigue level to a descriptive string."""
    if fatigue_level <= 0:
        return "None"
    elif fatigue_level < 5:
        return "Very Low"
    elif fatigue_level < 25:
        return "Low"
    elif fatigue_level < 50:
        return "Moderate"
    elif fatigue_level < 70:
        return "High"
    elif fatigue_level < 90:
        return "Very High"
    elif fatigue_level == 100:
        return "Exhausted"