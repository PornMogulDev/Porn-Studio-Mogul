    
from dataclasses import dataclass

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