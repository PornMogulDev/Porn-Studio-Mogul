from dataclasses import dataclass, field
from typing import List

# --- SHOT SCENE DETAILS ---
@dataclass
class FinancialViewModel:
    """Holds all pre-formatted strings for the financial summary."""
    expenses_html: str
    revenue_html: str
    profit_html: str
    market_interest_html: str

@dataclass
class EditingOptionViewModel:
    """Holds data for a single post-production editing option."""
    tier_id: str
    name: str
    tooltip: str
    info_text: str
    is_checked: bool

@dataclass
class PostProductionViewModel:
    """Holds all data needed to build the post-production tab."""
    is_visible: bool
    options: List[EditingOptionViewModel] = field(default_factory=list)