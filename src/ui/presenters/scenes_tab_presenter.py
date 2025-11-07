from typing import TYPE_CHECKING, List, Optional
from PyQt6.QtCore import QObject, pyqtSlot

from core.interfaces import IGameController
from data.game_state import Scene
from ui.view_models import SceneViewModel

if TYPE_CHECKING:
    from ui.ui_manager import UIManager
    from ui.tabs.scenes_tab import ScenesTab

class ScenesTabPresenter(QObject):
    """
    Presenter for the ScenesTab. It handles fetching scene data, processing it
    into view models, managing UI state, and responding to user interactions.
    """
    def __init__(self, controller: IGameController, view: 'ScenesTab', ui_manager: 'UIManager', parent=None):
        super().__init__(parent)
        self.controller = controller
        self.view = view
        self.ui_manager = ui_manager

        # --- Signal Connections ---
        self.controller.signals.scenes_changed.connect(self.refresh_data)
        
        self.view.selection_changed.connect(self.on_selection_changed)
        self.view.manage_button_clicked.connect(self.on_manage_button_clicked)
        self.view.item_double_clicked.connect(self.on_item_double_clicked)

    def load_initial_data(self):
        """Entry point called by the MainWindow to perform the first data load."""
        self.refresh_data()

    @pyqtSlot()
    def refresh_data(self):
        """Fetches all shot scenes, processes them, and updates the view."""
        raw_scenes = self.controller.get_shot_scenes()
        view_models = self._create_view_models(raw_scenes)
        
        # Pass both raw scenes (for sorting model) and view models (for display model)
        self.view.update_scene_list(view_models, raw_scenes)
        
        # After a refresh, the selection is cleared, so update buttons accordingly.
        self.on_selection_changed(None)

    def _create_view_models(self, scenes: List[Scene]) -> List[SceneViewModel]:
        """
        Converts a list of raw Scene data objects into a list of display-ready
        SceneViewModel objects. This isolates data processing logic from the view.
        """
        view_models = []
        for scene in scenes:
            # --- Date String ---
            if scene.scheduled_year == -1 or scene.scheduled_week == -1:
                date_str = "Unscheduled"
            else:
                date_str = f"W{scene.scheduled_week}, {scene.scheduled_year}"

            # --- Revenue String ---
            revenue_str = f"${scene.revenue:,}" if scene.status == 'released' else "N/A"

            # --- Cast String (Complex logic now lives here) ---
            if not scene.final_cast:
                cast_str = f"({len(scene.virtual_performers)} roles uncast)"
            else:
                talent_aliases = []
                for talent_id in scene.final_cast.values():
                    talent = self.controller.get_talent_by_id(talent_id)
                    talent_aliases.append(talent.alias if talent else f"ID {talent_id}?")
                cast_str = ", ".join(talent_aliases)

            vm = SceneViewModel(
                scene_id=scene.id,
                status=scene.status,
                title=scene.title,
                display_status=scene.display_status,
                date_str=date_str,
                revenue_str=revenue_str,
                cast_str=cast_str
            )
            view_models.append(vm)
        return view_models

    @pyqtSlot(object)
    def on_selection_changed(self, selected_vm: Optional[SceneViewModel]):
        """Updates the state of the main action button based on the selected scene."""
        if not selected_vm:
            self.view.update_button_state("Release Selected Scene", is_enabled=False)
            return

        if selected_vm.status == 'ready_to_release':
            self.view.update_button_state("Release Scene", is_enabled=True)
        elif selected_vm.status == 'shot':
            self.view.update_button_state("Manage Post-Production", is_enabled=True)
        else:
            self.view.update_button_state("Release Selected Scene", is_enabled=False)

    @pyqtSlot(object)
    def on_manage_button_clicked(self, selected_vm: SceneViewModel):
        """Handles the logic when the main action button is clicked."""
        if not selected_vm:
            return
        
        if selected_vm.status == 'ready_to_release':
            self.controller.release_scene(selected_vm.scene_id)
        elif selected_vm.status == 'shot':
            # This action opens the same details dialog as a double-click.
            self.ui_manager.show_shot_scene_details(selected_vm.scene_id, initial_tab="post-production")

    @pyqtSlot(int)
    def on_item_double_clicked(self, scene_id: int):
        """Opens the scene details dialog when an item is double-clicked."""
        self.ui_manager.show_shot_scene_details(scene_id)