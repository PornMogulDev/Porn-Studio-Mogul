from PyQt6.QtCore import QObject

from ui.view_models import AIStudioViewModel, AISceneViewModel
from utils import time_utils

class AIStudiosTabPresenter(QObject):
    """
    Presenter for the AI Studios Tab.
    Handles data fetching and view updates.
    """
    def __init__(self, controller, view, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.view = view
        
        self._connect_signals()
    
    def _connect_signals(self):
        # View events
        self.view.list_widget.studio_selected.connect(self._on_studio_selected)
        
        # Controller events (refresh data when week advances)
        self.controller.signals.time_changed.connect(self.refresh)

    def load_initial_data(self):
        self.refresh()

    def refresh(self):
        # Fetch raw data
        studios = self.controller.get_all_ai_studios()
        
        # Create ViewModels
        vms = []
        for s in studios:
            vms.append(AIStudioViewModel(
                id=s.id,
                name=s.name,
                location=s.location,
                money_str=f"${s.money:,}",
                active_status_str="Active" if s.active else "Inactive"
            ))
            
        self.view.list_widget.set_studios(vms)
        self.view.details_widget.clear()
        self.view.scenes_widget.clear()

    def _on_studio_selected(self, studio_id: int):
        # 1. Fetch Studio Details (re-using query_service for simplicity, 
        # normally we might have a specific get_studio_by_id if detail was huge)
        studios = self.controller.get_all_ai_studios()
        studio = next((s for s in studios if s.id == studio_id), None)
        
        if studio:
            self.view.details_widget.display_studio(studio)
            
            # 2. Fetch Scenes
            scenes = self.controller.get_ai_studio_scenes(studio_id)
            scene_vms = []
            for scene in scenes:
                year, week = time_utils.from_absolute(scene.released_absolute_week)
                date_str = f"Y{year} W{week}" if scene.released_absolute_week else "In Prod"
                
                scene_vms.append(AISceneViewModel(
                    id=scene.id,
                    title=scene.title,
                    date_str=date_str,
                    quality_score_str=f"{scene.quality_score:.1f}",
                    market_group=scene.target_market_group
                ))
            
            self.view.scenes_widget.set_scenes(scene_vms)