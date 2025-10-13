from typing import Tuple
from PyQt6.QtGui import QColor

from game_state import Talent
from settings_manager import SettingsManager

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

def format_physical_attribute(talent: Talent) -> Tuple[bool, str]:
    """
    Formats the primary physical attribute (boob cup or dick size) for display.
    Reads the unit system directly from the SettingsManager.
    
    Returns:
        A tuple of (is_visible, display_text).
    """
    settings = SettingsManager() # Get singleton instance
    unit_system = settings.get_setting("unit_system", "imperial")

    if talent.gender == "Female" and talent.boob_cup:
        return True, f"{talent.boob_cup} Cup Size"
    elif talent.gender == "Male" and talent.dick_size is not None:
        if unit_system == 'metric':
            cm_value = talent.dick_size * 2.54
            return True, f"{cm_value:.1f} cm Dick"
        else: # imperial
            return True, f"{talent.dick_size}\" Dick"
    return False, "N/A"