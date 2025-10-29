from dataclasses import dataclass
from typing import Tuple

from database.db_models import TalentDB

@dataclass
class TalentFilterCache:
    """A lightweight container for pre-calculated talent data used for fast filtering."""
    talent_db: TalentDB
    perf_range: Tuple[int, int]
    act_range: Tuple[int, int]
    stam_range: Tuple[int, int]