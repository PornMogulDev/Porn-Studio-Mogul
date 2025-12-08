from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

@dataclass
class ContentTagInput:
    """
    Represents a single content element (Action Segment or Physical Tag)
    normalized for revenue calculation.
    """
    tag_name: str
    tag_type: str  # 'Action', 'Physical'
    quality: float  # Normalized 0.0 to 1.0
    weight: float   # Normalized importance weight
    orientation: Optional[str] = None
    concept: Optional[str] = None
    # For scaling rules (e.g., counts of specific roles in a segment)
    scaling_params: Dict[str, int] = field(default_factory=dict)

@dataclass
class RevenueInput:
    """
    Standardized input DTO for the RevenueCalculator.
    Decouples the calculator from the GameState Scene/Talent objects.
    """
    title: str
    focus_target: str
    dom_sub_level: int
    total_runtime_minutes: int
    
    # Thematic tags (additive bonuses)
    global_tags: List[str] = field(default_factory=list)
    
    # Action/Physical tags (multiplicative scores)
    content_tags: List[ContentTagInput] = field(default_factory=list)
    
    # Pre-calculated average popularity per market group
    # Key: Market Group Name, Value: Average Popularity Score
    star_power_scores: Dict[str, float] = field(default_factory=dict)