from dataclasses import dataclass
from typing import Tuple

from database.db_models import TalentDB

@dataclass
class TalentFilterCache:
    """A lightweight container for pre-calculated talent data used for fast filtering and display."""
    talent_db: TalentDB
    # Fuzzed skill ranges for filtering
    perf_range: Tuple[int, int]
    act_range: Tuple[int, int]
    stam_range: Tuple[int, int]
    # Additional fuzzed skills for display (eliminates duplicate calculation in table model)
    dom_range: Tuple[int, int]
    sub_range: Tuple[int, int]
    # Pre-calculated popularity
    popularity: int