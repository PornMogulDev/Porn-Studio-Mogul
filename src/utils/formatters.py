from typing import Tuple, Optional, Union
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

def format_dick_size(inches_val: float, unit_system: str) -> str:
    """
    Formats dick size (provided in inches) to the chosen unit system, without decimals.
    """
    if unit_system == 'metric':
        cm = inches_val * 2.54
        return f"{round(cm)} cm"
    else:  # Imperial is the default
        return f"{round(inches_val)}\""

def format_physical_attribute(talent: Talent, unit_system: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Determines the primary physical attribute and formats it for display.
     
     Returns:
        A tuple of (attribute_name, formatted_value). E.g., ("Dick", '7.1"').
        Returns (None, None) if no relevant attribute is present.
    """
    if talent.gender == "Female" and talent.cup_size:
        return "Cup Size", f"{talent.cup_size}"
    elif talent.gender == "Male" and talent.dick_size is not None:
        return ("Dick Size", format_dick_size(talent.dick_size, unit_system))
    return None, None

def get_fuzzed_skill_range(skill_value: float, experience: float, talent_id: int) -> Union[int, Tuple[int, int]]:
    """
    Returns a fuzzed skill range or accurate value based on experience.
    The range width is fixed, but its position relative to the true value varies.

    Args:
        skill_value: The true skill value (0-100).
        experience: The talent's experience (0-100).
        talent_id: The talent's unique ID, used for deterministic randomness.

    Returns:
        A tuple (min, max) for a fuzzed range, or a single int for an accurate value.
    """
    true_val = round(skill_value)

    if experience < 20: range_width = 40
    elif experience < 40: range_width = 30
    elif experience < 60: range_width = 20
    elif experience < 80: range_width = 10
    elif experience < 95: range_width = 5
    else: return true_val

    # Use the talent's ID to create a deterministic, pseudo-random offset.
    # This ensures the range is consistent for a given talent at a given experience level.
    offset = (talent_id * 13) % (range_width + 1)
    min_val = true_val - offset
    max_val = min_val + range_width

    clamped_min = max(0, min_val)
    clamped_max = min(100, max_val)

    if clamped_min == 0: clamped_max = min(100, range_width)
    if clamped_max == 100: clamped_min = max(0, 100 - range_width)

    return (clamped_min, clamped_max)

def format_skill_range(skill_range: Union[int, Tuple[int, int]]) -> str:
    """Formats the output of get_fuzzed_skill_range into a display string."""
    if isinstance(skill_range, int): return str(skill_range)
    if isinstance(skill_range, tuple): return f"{skill_range[0]} - {skill_range[1]}"
    return "N/A"
    
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