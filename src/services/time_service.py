from sqlalchemy.orm import selectinload
from data.game_state import GameState
from data.data_manager import DataManager
from services.scene_service import SceneService
from services.talent_service import TalentService
from services.market_service import MarketService
from database.db_models import GameInfoDB, SceneDB, TalentDB

class TimeService:
    def __init__(self, db_session, game_state: GameState, signals, scene_service: SceneService, 
                 talent_service: TalentService, market_service: MarketService, 
                 data_manager: DataManager):
        self.session = db_session
        self.game_state = game_state # Still needed for week, year, money
        self.signals = signals
        self.scene_service = scene_service
        self.talent_service = talent_service
        self.market_service = market_service
        self.data_manager = data_manager

    def process_week_advancement(self) -> dict:
        """
        Advances the game by one week by running a series of DB queries and updates.
        This process may be paused if an interactive event occurs during a scene shoot.
        """
        changes = {"scenes": False, "market": False, "talent_pool": False}
        current_date_val = self.game_state.year * 52 + self.game_state.week

        # Decay talent popularity
        decay_rate = self.data_manager.game_config.get("popularity_decay_rate_weekly", 0.995)
        # Use selectinload to efficiently load all related popularity scores and avoid N+1 queries
        talents_to_update = self.session.query(TalentDB).options(
            selectinload(TalentDB.popularity_scores)
        ).all()
        for talent in talents_to_update:
            # Instead of replacing a dictionary, we iterate through the related objects and update them.
            for pop_entry in talent.popularity_scores:
                pop_entry.score *= decay_rate
        
        # Recover talent from fatigue
        fatigued_talents = self.session.query(TalentDB).filter(TalentDB.fatigue > 0).all()
        for talent in fatigued_talents:
            fatigue_end_val = talent.fatigue_end_year * 52 + talent.fatigue_end_week
            if current_date_val >= fatigue_end_val:
                talent.fatigue = 0
                talent.fatigue_end_week = 0
                talent.fatigue_end_year = 0

        # Recover market saturation
        if self.market_service.recover_all_market_saturation():
            changes["market"] = True
            
        # Shoot scheduled scenes
        scenes_to_shoot = self.session.query(SceneDB).filter_by(
            status='scheduled',
            scheduled_week=self.game_state.week,
            scheduled_year=self.game_state.year
        ).all()
        for scene_db in scenes_to_shoot:
            event_occurred = self.scene_service.shoot_scene(scene_db)
            if event_occurred:
                # An event has paused execution. Stop the entire week advancement.
                # The controller will handle resuming the process.
                changes["scenes"] = True # A scene was started, so changes occurred
                return changes
            changes["scenes"] = True

        # Update scenes in post-production
        editing_scenes = self.session.query(SceneDB).filter_by(status='in_editing').all()
        for scene_db in editing_scenes:
            scene_db.weeks_remaining -= 1
            if scene_db.weeks_remaining <= 0:
                self.scene_service.calculation_service.apply_post_production_effects(scene_db)
                changes["scenes"] = True

        # Advance time
        self.game_state.week += 1
        if self.game_state.week > 52:
            self.game_state.week = 1
            self.game_state.year += 1
            for talent in talents_to_update:
                talent.age += 1
                # Create a new dataclass instance reflecting the updated age
                updated_talent_obj = talent.to_dataclass(Talent) 
                new_affinities = self.talent_service.recalculate_talent_age_affinities(updated_talent_obj)
                talent.tag_affinities = new_affinities
            changes["talent_pool"] = True
        
        # Update GameInfo in DB
        week_info = self.session.query(GameInfoDB).filter_by(key='week').one()
        year_info = self.session.query(GameInfoDB).filter_by(key='year').one()
        week_info.value, year_info.value = str(self.game_state.week), str(self.game_state.year)
        
        return changes