from enum import Enum

class TraitModifiers(Enum):
    """
    Central registry of modifier keys used in Trait definitions.
    Use these Enums in code to prevent string typos.
    """
    # Financials
    TRAVEL_COST_MULTIPLIER = "travel_cost_multiplier"
    CONTRACT_SALARY_MULTIPLIER = "contract_salary_multiplier"
    
    # Gameplay / Tour
    TOUR_DESIRE_FLAT = "tour_desire_flat"
    
    # Performance
    PERFORMANCE_BONUS = "performance_bonus"