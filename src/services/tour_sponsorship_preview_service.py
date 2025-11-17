import logging
from typing import List, Dict

from data.data_manager import DataManager
from services.query.game_query_service import GameQueryService
from services.query.talent_query_service import TalentQueryService
from services.tour_feasibility_service import TourFeasibilityService
from services.calculation.upfront_tour_cost_calculator import UpfrontTourCostCalculator
from services.models.results import TourSponsorshipPreviewResult

logger = logging.getLogger(__name__)

class TourSponsorshipPreviewService:
    """
    An orchestrator service for previewing the feasibility and costs of a
    player-sponsored tour. It fetches all necessary data and delegates
    logic and calculations to the appropriate services.
    """
    def __init__(self, data_manager: DataManager, query_service: GameQueryService,
                 talent_query_service: TalentQueryService, feasibility_service: TourFeasibilityService,
                 cost_calculator: UpfrontTourCostCalculator):
        self.data_manager = data_manager
        self.query_service = query_service
        self.talent_query_service = talent_query_service
        self.feasibility_service = feasibility_service
        self.cost_calculator = cost_calculator

    def generate_preview(self, talent_id: int, roles: List[Dict], studio_location: str) -> TourSponsorshipPreviewResult:
        """
        Calculates all necessary data for a tour sponsorship negotiation.
        """
        if not roles:
            return TourSponsorshipPreviewResult(is_feasible=False, refusal_reason="No roles were selected for the tour.")

        # --- 1. Orchestration: Fetch all required data ---
        # Fetch the DB object, as the feasibility service needs to access the popularity_scores relationship.
        talent_db_model = self.query_service.get_talent_by_id_db(talent_id)
        if not talent_db_model:
            return TourSponsorshipPreviewResult(is_feasible=False, refusal_reason="Talent not found.")

        scene_ids = [r['scene_id'] for r in roles]
        scenes_dc = self.query_service.get_multiple_scenes_by_ids(scene_ids)
        if len(scenes_dc) != len(scene_ids):
            return TourSponsorshipPreviewResult(is_feasible=False, refusal_reason="One or more selected scenes could not be found.")

        # --- 2. Orchestration: Determine tour parameters ---
        dates = [(s.scheduled_year * 52 + s.scheduled_week) for s in scenes_dc]
        min_date, max_date = min(dates), max(dates)
        start_year, week_offset = divmod(min_date - 1, 52)
        start_week = week_offset + 1
        duration_weeks = (max_date - min_date) + 1

        # --- 3. Orchestration: Check for schedule conflicts ---
        end_year = start_year + (start_week + duration_weeks - 2) // 52
        all_bookings = self.talent_query_service.get_talent_bookings_for_year(talent_id, start_year)
        if end_year > start_year:
            next_year_bookings = self.talent_query_service.get_talent_bookings_for_year(talent_id, end_year)
            all_bookings.update(next_year_bookings)
        
        conflict_reason = self.feasibility_service.check_schedule_conflict(
            start_week, start_year, duration_weeks, all_bookings
        )
        if conflict_reason:
            return TourSponsorshipPreviewResult(is_feasible=False, refusal_reason=conflict_reason)

        # --- 4. Orchestration: Determine accommodation needs and acceptable options ---
        required_tier_id = self.feasibility_service.determine_accommodation_tier(talent_db_model)
        if not required_tier_id:
            return TourSponsorshipPreviewResult(is_feasible=False, refusal_reason="No suitable accommodation found for their standards.")

        required_tier_cost = self.data_manager.accommodation_tiers.get(required_tier_id, {}).get('cost_per_week', 0)

        acceptable_options = [
            tier for tier in self.data_manager.accommodation_tiers.values()
            if tier['cost_per_week'] >= required_tier_cost
        ]
        acceptable_options.sort(key=lambda x: x['cost_per_week'])

        # --- 5. Orchestration: Calculate base travel cost ---
        travel_cost = self.cost_calculator.calculate_travel_cost(talent_db_model.base_location, studio_location)

        # --- 6. Assemble and return the final DTO ---
        return TourSponsorshipPreviewResult(
            is_feasible=True,
            destination_location=studio_location,
            start_week=start_week,
            start_year=start_year,
            duration_weeks=duration_weeks,
            travel_cost=travel_cost,
            accommodation_options=acceptable_options,
            required_accommodation_tier_id=required_tier_id,
            all_accommodation_tiers=self.data_manager.accommodation_tiers
        )