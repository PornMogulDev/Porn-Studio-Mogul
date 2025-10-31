    
from dataclasses import dataclass, field
from typing import Dict

@dataclass(frozen=True)
class HiringConfig:
    """Configuration values for talent hiring and cost calculation."""
    concurrency_default_limit: int
    refusal_threshold: float
    orientation_refusal_threshold: float
    pickiness_popularity_scalar: float
    pickiness_ambition_scalar: float
    base_talent_demand: int
    demand_perf_divisor: float
    median_ambition: float
    ambition_demand_divisor: float
    popularity_demand_scalar: float
    minimum_talent_demand: int

@dataclass(frozen=True)
class MarketConfig:
    saturation_recovery_rate: float

@dataclass(frozen=True)
class SceneCalculationConfig:
    """Configuration values for scene shooting, quality, and revenue calculations."""
    # Stamina & Fatigue
    stamina_to_pool_multiplier: int
    base_fatigue_weeks: int
    in_scene_penalty_scalar: float
    fatigue_penalty_scalar: float
    
    # Skills & Experience
    maximum_skill_level: float

    # Quality Calculation
    scene_quality_base_acting_weight: float
    scene_quality_min_acting_weight: float
    scene_quality_max_acting_weight: float
    protagonist_contribution_weight: float
    chemistry_performance_scalar: float
    scene_quality_ds_weights: Dict[int, float]
    scene_quality_min_performance_modifier: float
    scene_quality_auto_tag_default_quality: float

    # Revenue Calculation
    base_release_revenue: int
    star_power_revenue_scalar: float
    saturation_spend_rate: float
    default_sentiment_multiplier: float
    revenue_weight_focused_physical_tag: float
    revenue_weight_default_action_appeal: float
    revenue_weight_auto_tag: float
    revenue_weight_default_action_appeal: float
    revenue_weight_auto_tag: float
    revenue_penalties: Dict = field(default_factory=dict)