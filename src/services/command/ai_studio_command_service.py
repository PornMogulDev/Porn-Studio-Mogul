import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from core.game_signals import GameSignals
from database.db_models import AIStudioDB, AISceneDB
from data.game_state import AIStudio
from data.data_manager import DataManager

logger = logging.getLogger(__name__)

class AIStudioCommandService:
    """
    Handles Database CRUD operations for AI Studios and their scenes.
    """
    def __init__(self, session_factory, signals: GameSignals, data_manager: DataManager):
        self.session_factory = session_factory
        self.signals = signals
        self.data_manager = data_manager

    def get_all_ai_studios(self) -> List[AIStudioDB]:
        """Retrieves all AI studios from the database."""
        session = self.session_factory()
        try:
            studios = session.query(AIStudioDB).filter_by(active=True).all()
            return studios
        finally:
            session.close()

    def get_studio_scene_count(self, session: Session, studio_id: int) -> int:
        """Counts total scenes created by a specific AI studio (for naming)."""
        return session.query(func.count(AISceneDB.id)).filter_by(ai_studio_id=studio_id).scalar()

    def create_ai_scene(self, session: Session, studio_id: int, title: str, 
                        current_week: int, target_market: str, quality: float) -> AISceneDB:
        """
        Records a new AI scene in production.
        Note: Operates within an existing transaction (passed session).
        """
        # Simple logic: 2 week production time for prototype
        release_week = current_week + 2
        
        scene = AISceneDB(
            ai_studio_id=studio_id,
            title=title,
            created_absolute_week=current_week,
            released_absolute_week=release_week,
            target_market_group=target_market,
            quality_score=quality
        )
        session.add(scene)
        return scene

    def get_scenes_releasing_this_week(self, session: Session, current_week: int) -> List[AISceneDB]:
        """Retrieves scenes scheduled for release in the current week."""
        return session.query(AISceneDB).filter_by(released_absolute_week=current_week).all()