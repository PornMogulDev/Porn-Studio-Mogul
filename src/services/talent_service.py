"""
This module is a temporary SHIM that provides backward compatibility for the
original TalentService. Its methods delegate to the new, specialized
GameQueryService and TalentCommandService.

This file will be DELETED once all dependents (like GameController) are updated
to use the new services directly.
"""
import logging
from typing import Dict, List, Optional

from data.game_state import Talent
from database.db_models import TalentDB
from services.query.game_query_service import GameQueryService
from services.command.talent_command_service import TalentCommandService

logger = logging.getLogger(__name__)

class TalentService:
    """Temporary Shim for TalentService."""
    def __init__(self, query_service: GameQueryService, command_service: TalentCommandService):
        self.query_service = query_service
        self.command_service = command_service

    def get_filtered_talents(self, all_filters: dict) -> List[TalentDB]:
        return self.query_service.get_filtered_talents(all_filters)

    def get_talent_by_id(self, talent_id: int) -> Optional[Talent]:
        return self.query_service.get_talent_by_id(talent_id)
    
    def get_talent_chemistry(self, talent_id: int) -> Dict[int, Dict]:
        return self.query_service.get_talent_chemistry(talent_id)

    def discover_and_create_chemistry(self, cast_talents: List[Talent], commit: bool = False):
        return self.command_service.discover_and_create_chemistry(cast_talents, commit)

    def update_popularity_from_scene(self, scene_id: int, commit: bool = False):
        return self.command_service.update_popularity_from_scene(scene_id, commit)

    def process_weekly_updates(self, current_date_val: int, new_year: bool) -> bool:
        return self.command_service.process_weekly_updates(current_date_val, new_year)