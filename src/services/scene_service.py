import logging
from typing import Dict, List, Optional

from data.game_state import Scene, ShootingBloc
from database.db_models import SceneDB
from services.query.game_query_service import GameQueryService
from services.command.scene_command_service import SceneCommandService

logger = logging.getLogger(__name__)

class SceneService:
    """
    This class is a temporary "shim" or "facade" during refactoring.
    It delegates calls to the new Query and Command services, allowing the
    rest of the application to be updated incrementally without breaking.
    """
    def __init__(self, query_service: GameQueryService, command_service: SceneCommandService):
        self.query_service = query_service
        self.command_service = command_service

    # --- UI Query Methods ---
    def get_blocs_for_schedule_view(self, year: int) -> List[ShootingBloc]:
        return self.query_service.get_blocs_for_schedule_view(year)

    def get_bloc_by_id(self, bloc_id: int) -> Optional[ShootingBloc]:
        return self.query_service.get_bloc_by_id(bloc_id)

    def get_shot_scenes(self) -> List[Scene]:
        return self.query_service.get_shot_scenes()

    def get_scene_for_planner(self, scene_id: int) -> Optional[Scene]:
        return self.query_service.get_scene_for_planner(scene_id)

    def get_scene_history_for_talent(self, talent_id: int) -> List[Scene]:
        return self.query_service.get_scene_history_for_talent(talent_id)
    
    def get_incomplete_scenes_for_week(self, week: int, year: int) -> List[Scene]:
        return self.query_service.get_incomplete_scenes_for_week(week, year)

    def get_castable_scenes_for_ui(self) -> List[Dict]:
        return self.query_service.get_castable_scenes_for_ui()

    def get_uncast_roles_for_scene_ui(self, scene_id: int) -> List[Dict]:
        return self.query_service.get_uncast_roles_for_scene_ui(scene_id)

    # --- CRUD and Logic Methods ---
    
    def cast_talent_for_role(self, talent_id: int, scene_id: int, virtual_performer_id: int, cost: int) -> bool:
        return self.command_service.cast_talent_for_role(talent_id, scene_id, virtual_performer_id, cost)

    def cast_talent_for_multiple_roles(self, talent_id: int, roles: List[Dict]) -> bool:
        return self.command_service.cast_talent_for_multiple_roles(talent_id, roles)

    def create_shooting_bloc(self, week: int, year: int, num_scenes: int, settings: Dict[str, str], cost: int, name: str, policies: List[str]) -> bool:
        return self.command_service.create_shooting_bloc(week, year, num_scenes, settings, cost, name, policies)

    def create_blank_scene(self, week: int, year: int) -> int:
        return self.command_service.create_blank_scene(week, year)

    def delete_scene(self, scene_id: int, penalty_percentage: float = 0.0, silent: bool = False, commit: bool = True) -> bool:
        return self.command_service.delete_scene(scene_id, penalty_percentage, silent, commit)

    def update_scene_full(self, scene_data: Scene) -> Dict:
        return self.command_service.update_scene_full(scene_data)
        
    def start_editing_scene(self, scene_id: int, editing_tier_id: str) -> tuple[bool, int]:
        return self.command_service.start_editing_scene(scene_id, editing_tier_id)

    def release_scene(self, scene_id: int) -> Dict:
        return self.command_service.release_scene(scene_id)

    def shoot_scene(self, scene_db: SceneDB) -> bool:
        return self.command_service.shoot_scene(scene_db)
    
    def _continue_shoot_scene(self, scene_id: int, shoot_modifiers: Dict):
        self.command_service._continue_shoot_scene(scene_id, shoot_modifiers)

    def process_weekly_post_production(self) -> List[SceneDB]:
        return self.command_service.process_weekly_post_production()