"""
This module defines dataclasses used as standardized "result objects" or
Data Transfer Objects (DTOs) for the scene calculation refactoring.

These models decouple the pure calculation logic from the database persistence
layer. Services and Calculators will receive game state dataclasses (e.g., Scene, Talent)
and return these result objects. The orchestrator service will then use these
results to update the database models.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum, auto

from data.game_state import Tour
from ui.view_models import ScheduleStatus

class EventAction(Enum):
    """Defines the next action to be taken after an event choice is resolved."""
    CONTINUE_SHOOT = auto()
    CANCEL_SCENE = auto()
    CHAIN_EVENT = auto()

@dataclass(frozen=True)
class EventResolutionResult:
    """Represents the outcome of resolving an interactive event choice."""
    next_action: EventAction
    shoot_modifiers: Dict = field(default_factory=dict)
    notification: Optional[str] = None
    chained_event_payload: Optional[Dict] = None # For CHAIN_EVENT action
    cancellation_penalty: float = 0.0 # For CANCEL_SCENE action

@dataclass(frozen=True)
class FatigueResult:
    """Represents the outcome of a fatigue calculation for a talent."""
    new_fatigue_level: int

@dataclass(frozen=True)
class TalentShootOutcome:
    """Aggregates all calculated changes for a single talent after a scene shoot."""
    talent_id: int
    stamina_cost: float
    fatigue_result: Optional[FatigueResult]
    stress_gain: float
    burnout_gain: float = 0.0
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
class ShootCalculationResult:
    """Consolidated results from all pure shoot calculators."""
    talent_outcomes: List[TalentShootOutcome]
    quality_result: SceneQualityResult
    discovered_tags: List[str]
    momentum_delta: float = 0.0
    stress_delta: float = 0.0

@dataclass(frozen=True)
class PostProductionResult:
    """Represents the outcome of applying post-production effects."""
    new_tag_qualities: Dict[str, float]
    new_performer_contributions: List[Dict[str, float | int | str]]
    revenue_modifier_details: Dict[str, float]

@dataclass(frozen=True)
class WeekAdvancementResult:
    """Represents the outcome of a week advancement process."""
    new_absolute_week: int
    new_money: int
    was_paused: bool = False
    scenes_shot: int = 0
    scenes_edited: int = 0
    market_changed: bool = False
    talent_pool_changed: bool = False

@dataclass(frozen=True)
class TourFeasibilityResult:
    """Represents the outcome of a tour feasibility check."""
    is_feasible: bool
    refusal_reason: Optional[str] = None
    total_upfront_cost: int = 0
    accommodation_tier_id: Optional[str] = None

@dataclass(frozen=True)
class TourSponsorshipPreviewResult:
    is_feasible: bool
    refusal_reason: Optional[str] = None
    destination_location: Optional[str] = None
    start_week: Optional[int] = None; start_year: Optional[int] = None
    minimum_duration_weeks: Optional[int] = None
    travel_cost: int = 0
    required_accommodation_tier_id: Optional[str] = None
    all_accommodation_tiers: Dict = field(default_factory=dict) # All tiers for reference

@dataclass
class ValidationResult:
    success: bool
    reason: Optional[str] = None

@dataclass
class WeeklyStatusResult:
    """DTO containing the calculated status for a specific week."""
    week_number: int
    status_enum: ScheduleStatus
    is_fatigued: bool = False
    booked_scene_titles: List[str] = field(default_factory=list)
    tour: Optional[Tour] = None
    is_on_cooldown: bool = False