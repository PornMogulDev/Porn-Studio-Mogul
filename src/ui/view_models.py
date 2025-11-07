from dataclasses import dataclass, field
from typing import List, Tuple, Optional

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

# --- MARKET TAB ---
@dataclass
class SentimentViewModel:
    """
    Holds display-ready data for a single sentiment (tag preference).
    This allows the view to be "dumb" and just render what it's given.
    """
    label: str # The tag name, or "???" if undiscovered.
    value_str: str # The pre-formatted value (e.g., "+0.25", "1.50x"), or "" if undiscovered.
    color: Optional[str]# The hex color code for the value (e.g., "#00FF00"), or None.

@dataclass
class MarketGroupViewModel:
    """
    Holds all the processed and formatted data required to display the
    details of a single market viewer group.
    """
    is_visible: bool = True
    title: str = ""
    attributes: List[Tuple[str, str]] = field(default_factory=list)
    orientation_sentiments: List[SentimentViewModel] = field(default_factory=list)
    dom_sub_sentiments: List[SentimentViewModel] = field(default_factory=list)
    thematic_sentiments: List[SentimentViewModel] = field(default_factory=list)
    physical_sentiments: List[SentimentViewModel] = field(default_factory=list)
    action_sentiments: List[SentimentViewModel] = field(default_factory=list)
    spillover_details: List[Tuple[str, str]] = field(default_factory=list)

# --- SCHEDULE TAB ---
@dataclass
class ScheduleSceneViewModel:
    """Holds display data for a single scene in the schedule tree."""
    display_text: str
    tooltip: str
    user_data: dict # e.g., {'type': 'scene', 'id': 123}

@dataclass
class ScheduleBlocViewModel:
    """Holds display data for a shooting bloc, including its scenes."""
    display_text: str
    tooltip: str
    user_data: dict # e.g., {'type': 'bloc', 'id': 45}
    scenes: List[ScheduleSceneViewModel] = field(default_factory=list)

@dataclass
class ScheduleWeekViewModel:
    """Holds display data for a week, including its shooting blocs."""
    display_text: str
    user_data: dict # e.g., {'type': 'week_header', 'week': 1, 'year': 1}
    blocs: List[ScheduleBlocViewModel] = field(default_factory=list)

# --- SCENES TAB ---
@dataclass
class SceneViewModel:
    """Holds all pre-formatted, display-ready data for a single scene in the table."""
    scene_id: int
    status: str
    title: str
    display_status: str
    date_str: str
    revenue_str: str
    cast_str: str

# --- SETTINGS DIALOG ---
@dataclass
class SettingsViewModel:
    """Holds the initial state of settings to populate the dialog."""
    unit_system: str
    theme: str
    font_family: str
    font_size: int