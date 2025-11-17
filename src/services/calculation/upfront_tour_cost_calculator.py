import logging
from typing import Dict

from data.data_manager import DataManager

logger = logging.getLogger(__name__)

class UpfrontTourCostCalculator:
    """
    A pure, stateless calculator for determining the upfront cost of a tour.
    It has no side effects and does not access the database.
    """
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager

    def calculate_travel_cost(self, origin_location: str, destination_location: str) -> int:
        """Calculates only the travel cost for a talent to a destination."""
        if origin_location == destination_location:
            return 0
        
        location_map = self.data_manager.get_location_to_region_map()
        origin_region = location_map.get(origin_location)
        dest_region = location_map.get(destination_location)
        
        if origin_region and dest_region and origin_region != dest_region:
            if cost_data := self.data_manager.travel_matrix.get(origin_region, {}).get(dest_region):
                return cost_data.get('cost', 0)
        return 0

    def calculate_total_upfront_cost(self, origin_location: str, destination_location: str,
                                     accommodation_tier_id: str, duration_weeks: int) -> Dict[str, int]:
        """
        Calculates the total upfront cost (Travel + Accommodation) for a tour.

        Returns:
            A dictionary with a breakdown of travel and accommodation costs.
        """
        # 1. Travel Cost
        travel_cost = self.calculate_travel_cost(origin_location, destination_location)
        
        # 2. Accommodation Cost
        accommodation_cost = 0
        if tier_data := self.data_manager.accommodation_tiers.get(accommodation_tier_id):
            accommodation_cost = tier_data['cost_per_week'] * duration_weeks
        
        total_cost = travel_cost + accommodation_cost
        
        return {
            "travel_cost": travel_cost,
            "accommodation_cost": accommodation_cost,
            "total_upfront_cost": total_cost
        }