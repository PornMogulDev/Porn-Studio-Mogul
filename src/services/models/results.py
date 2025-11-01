"""
This module defines dataclasses used as standardized "result objects" or
Data Transfer Objects (DTOs) for the scene calculation refactoring.

These models decouple the pure calculation logic from the database persistence
layer. Calculators will receive game state dataclasses (e.g., Scene, Talent)
and return these result objects. The orchestrator service will then use these
results to update the database models.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass(frozen=True)
class FatigueResult:
    """Represents the outcome of a fatigue calculation for a talent."""
    new_fatigue_level: int
    fatigue_end_week: int
    fatigue_end_year: int

@dataclass(frozen=True)
class TalentShootOutcome:
    """Aggregates all calculated changes for a single talent after a scene shoot."""
    talent_id: int
    stamina_cost: float
    fatigue_result: Optional[FatigueResult]
    skill_gains: Dict[str, float] = field(default_factory=dict)
    experience_gain: float = 0.0

@dataclass(frozen=True)
class SceneQualityResult:
    """Holds the calculated quality scores for a scene."""
    tag_qualities: Dict[str, float]
    performer_contributions: List[Dict[str, float | int | str]] # e.g. {'talent_id': X, 'key': Y, 'score': Z}

@dataclass(frozen=True)
class SceneRevenueResult:
    """Contains all results from the revenue calculation for a released scene."""
    total_revenue: int
    viewer_group_interest: Dict[str, float]
    revenue_modifier_details: Dict[str, float]
    market_saturation_updates: Dict[str, float] # Maps group_name to its saturation cost for this scene

@dataclass(frozen=True)
class PostProductionResult:
    """Represents the outcome of applying post-production effects."""
    new_tag_qualities: Dict[str, float]
    new_performer_contributions: List[Dict[str, float | int | str]]
    revenue_modifier_details: Dict[str, float]

@dataclass(frozen=True)
class WeekAdvancementResult:
    """Represents the outcome of a week advancement process."""
    new_week: int
    new_year: int
    was_paused: bool = False
    scenes_shot: int = 0
    scenes_edited: int = 0
    market_changed: bool = False
    talent_pool_changed: bool = False