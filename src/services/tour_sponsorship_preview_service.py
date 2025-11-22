import logging
from typing import List, Dict

from data.data_manager import DataManager
from services.query.game_query_service import GameQueryService
from services.query.talent_query_service import TalentQueryService
from services.tour_feasibility_service import TourFeasibilityService
from services.calculation.upfront_tour_cost_calculator import UpfrontTourCostCalculator
from services.models.results import TourSponsorshipPreviewResult
from utils import time_utils

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
        dates = [s.scheduled_absolute_week for s in scenes_dc]
        min_absolute_week, max_absolute_week = min(dates), max(dates)
        start_absolute_week = min_absolute_week
        duration_weeks = (max_absolute_week - min_absolute_week) + 1

        # --- 3. Orchestration: Check for schedule conflicts ---
        # Fetch existing bookings for the entire proposed tour duration
        all_bookings = self.talent_query_service.get_talent_bookings_by_absolute_week(
            talent_id, start_absolute_week, max_absolute_week
        )
        
        conflict_reason = self.feasibility_service.check_schedule_conflict(
            start_absolute_week, duration_weeks, all_bookings
        )
        if conflict_reason:
            return TourSponsorshipPreviewResult(is_feasible=False, refusal_reason=conflict_reason)

        # --- 4. Orchestration: Determine accommodation needs and acceptable options ---
        required_tier_id = self.feasibility_service.determine_accommodation_tier(talent_db_model)
        if not required_tier_id:
            return TourSponsorshipPreviewResult(is_feasible=False, refusal_reason="No suitable accommodation found for their standards.")

        # --- 5. Orchestration: Calculate base travel cost ---
        travel_cost = self.cost_calculator.calculate_travel_cost(talent_db_model.base_location, studio_location)

        # --- 6. Assemble and return the final DTO ---
        _start_year, _start_week = time_utils.from_absolute(start_absolute_week)
        return TourSponsorshipPreviewResult(
            is_feasible=True,
            destination_location=studio_location,
            start_week=_start_week,
            start_year=_start_year,
            minimum_duration_weeks=duration_weeks,
            travel_cost=travel_cost,
            required_accommodation_tier_id=required_tier_id,
            all_accommodation_tiers=self.data_manager.accommodation_tiers
        )