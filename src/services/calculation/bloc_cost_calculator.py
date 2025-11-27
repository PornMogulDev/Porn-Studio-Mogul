import logging
from typing import Dict, List, Any
from data.data_manager import DataManager

logger = logging.getLogger(__name__)

class BlocCostCalculator:
    """
    Calculates the total upfront financial cost of a Shooting Bloc.
    """
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager

    def calculate_shooting_bloc_cost(self, 
                                     location_id: str,
                                     department_budgets: Dict[str, int],
                                     crew_assignments: Dict[str, Dict[str, Any]],
                                     picture_set_settings: Dict[str, Any],
                                     policies: List[str]) -> int:
        """
        Calculates total cost for the entire shooting block.
        
        Args:
            department_budgets: Dictionary of {department_id: total_dollar_amount_for_block}
            crew_assignments: Dictionary of {slot_id: {'type': 'freelancer', 'budget': amount}}
            policies: List of policy IDs enabled for this block.
        """
        total_cost = 0

        # 1. Department Budgets (Includes Location Logistics)
        # These are passed as total dollar amounts allocated for the whole block
        total_cost += sum(department_budgets.values())

        # 2. Crew Costs (Freelancer hiring fees for the block)
        for _, assignment in crew_assignments.items():
            if assignment.get('type') == 'freelancer':
                total_cost += assignment.get('budget', 0)

        # 3. Picture Set Costs 
        # Specific costs are typically handled via the Photographer crew slot or 
        # specific department allocations, but this hook remains for specific logic.
        pass

        # 4. Policies (Cost per block)
        for policy_id in policies:
            policy = self.data_manager.on_set_policies_data.get(policy_id)
            if policy:
                total_cost += policy.get('cost_per_bloc', 0)

        return total_cost