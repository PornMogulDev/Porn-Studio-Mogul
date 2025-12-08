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
                
                # Format Tags: Collect Global, Action, and Physical (keys of assigned_tags)
                # We filter assigned_tags to exclude Action tags since they are already in action_segments list if we want duplicates,
                # but better to just show unique significant tags.
                all_tags = []
                if scene.global_tags: all_tags.extend(scene.global_tags)
                if scene.action_segments: all_tags.extend(scene.action_segments)
                
                # Physical tags are in assigned_tags, but action tags might be there too (with qualities).
                # We want physicals specifically.
                # Since we don't have the tag defs here easily without querying, we'll just list 
                # keys from assigned_tags that AREN'T in action_segments.
                physical_tags = [t for t in scene.assigned_tags.keys() if t not in scene.action_segments]
                all_tags.extend(physical_tags)

                scene_vms.append(AISceneViewModel(
                    id=scene.id,
                    title=scene.title,
                    date_str=date_str,
                    orientation=scene.orientation,
                    dynamic_level_str=str(scene.dom_sub_dynamic_level),
                    tags_str=", ".join(all_tags),
                    market_group=scene.focus_target,
                    revenue_str=f"${scene.revenue:,}"
                ))
            
            self.view.scenes_widget.set_scenes(scene_vms)