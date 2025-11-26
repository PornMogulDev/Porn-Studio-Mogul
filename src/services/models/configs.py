    
from dataclasses import dataclass, field
from typing import Dict, List

@dataclass(frozen=True)
class HiringConfig:
    """Configuration values for talent hiring and cost calculation."""
    location_to_location_cost: int
    location_to_location_fatigue: int
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
    max_scenes_per_week_base: int
    max_scenes_per_week_ambition_modifier: float
    fatigue_refusal_threshold: int
    burnout_penalty_scenes: int
    rush_fee_multiplier: float
    bulk_discount_tiers: Dict[int, float]
    hazard_pay_modifiers: Dict[int, float]
    total_budget_refusal_thresholds: Dict[int, int]
    department_budget_refusal_thresholds: Dict[str, Dict[int, int]]

@dataclass(frozen=True)
class MarketConfig:
    saturation_recovery_rate: float
    discovery_interest_threshold: float
    discoveries_per_scene: int

@dataclass(frozen=True)
class ProductionConfig:
    """Configuration values for production logistics, budgeting, and simulation."""
    # Budgeting
    budget_min_penalty_multiplier: float
    budget_overspend_penalty_factor: float
    budget_efficiency_floor: float
    linear_curve_divisor: float
    exponential_curve_exponent: float
    step_curve_thresholds: Dict[float, float] # e.g. {0.25: 0.2, 0.5: 0.5}

    # Crew Generation
    crew_skill_baseline_multiplier: int # Efficiency * 50 = Skill
    crew_skill_sigma: int # Random variance
    
    # Bloc Simulation
    bloc_base_momentum: float
    bloc_base_stress: float
    momentum_bonus_threshold: float
    momentum_bonus_multiplier: float
    momentum_penalty_threshold: float
    momentum_penalty_multiplier: float

@dataclass(frozen=True)
class SceneCalculationConfig:
    """Configuration values for scene shooting, quality, and revenue calculations."""
    # Stamina & Fatigue
    stamina_to_pool_multiplier: int
    in_scene_penalty_scalar: float
    fatigue_penalty_scalar: float
    fatigue_passive_decay_rate: int
    fatigue_active_recovery_bonus: int
    fatigue_stamina_recovery_modifier: float
    
    # Stress & Burnout
    base_acting_stress: float
    multitasking_stress_multiplier: float  # e.g., 0.5 (adds 50% per extra role)
    introvert_crowd_penalty: float
    craft_services_stress_relief_scalar: float # e.g., 5.0 per efficiency point
    max_stress_threshold: float # 100.0
    burnout_conversion_rate: float # How much overflow stress becomes burnout (e.g., 0.1)
    
    # Skills & Experience
    maximum_skill_level: float
    skill_gain_base_rate: float
    skill_gain_curve_steepness: float
    exp_gain_base_rate: float
    exp_gain_curve_steepness: float
    ds_skill_gain_base_rate: float
    ds_skill_gain_disposition_multiplier: float
    ds_skill_gain_dynamic_level_multipliers: Dict[int, float]
    age_based_affinity_rules: List[Dict]
    popularity_gain_scalar: float

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
    revenue_penalties: Dict = field(default_factory=dict)

@dataclass(frozen=True)
class ContractConfig:
    """Configuration values for exclusive contracts."""
    fallback_salary_multiplier: float
    preference_salary_floor: float
    lock_in_premium: float
    initial_compliance: int
    compliance_max: int
    compliance_high_pref_threshold: float
    compliance_low_pref_threshold: float
    compliance_bonus: int
    compliance_penalty: int
    disposition_salary_weight: float
    skill_salary_weight: float

@dataclass
class TourConfig:
    batch_size: int # e.g., 4 (process 25% of talent per week)
    autonomous_fatigue_limit: int
    cooldown_weeks: int
    location_variety_penalty: int
    base_tour_desire: float 
    tour_desire_threshold: float 
    workload_desire_modifier: float # e.g., 10.0 per booking variance
    min_tour_duration: int
    max_tour_duration: int