"""
Utility functions for handling game time conversions between (year, week)
and a single 'absolute_week' integer.
"""
from typing import Tuple

# This value should ideally be read from game_config.json,
# but for simplicity in this utility, we'll define it as a constant.
# It must be kept in sync with the value in `data/game_config.json`.
WEEKS_PER_YEAR = 52
STARTING_YEAR = 2010

def to_absolute(year: int, week: int) -> int:
    """Converts (year, week) to an absolute week count, starting from 1."""
    if year < STARTING_YEAR:
        raise ValueError(f"Year {year} is before starting year {STARTING_YEAR}")
    if not 1 <= week <= WEEKS_PER_YEAR:
        raise ValueError(f"Week {week} must be between 1 and {WEEKS_PER_YEAR}")
        
    return (year - STARTING_YEAR) * WEEKS_PER_YEAR + week

def from_absolute(absolute_week: int) -> Tuple[int, int]:
    """Converts an absolute week count (starting from 1) to (year, week)."""
    if absolute_week <= 0:
        raise ValueError(f"Absolute week must be positive, but got {absolute_week}")
    
    # (absolute_week - 1) makes the calculation 0-indexed
    year_offset = (absolute_week - 1) // WEEKS_PER_YEAR
    week = (absolute_week - 1) % WEEKS_PER_YEAR + 1
    year = STARTING_YEAR + year_offset
    return year, week

def is_new_year_roll_over(absolute_week: int) -> bool:
    """
    Checks if the given absolute_week is the first week of a year,
    signaling a year roll-over event.
    """
    if absolute_week <= 1:
        return False
    # A new year starts when the 0-indexed week count is a multiple of WEEKS_PER_YEAR.
    # e.g., abs_week 53 -> (53-1) = 52. 52 % 52 == 0. This is a new year.
    return (absolute_week - 1) % WEEKS_PER_YEAR == 0