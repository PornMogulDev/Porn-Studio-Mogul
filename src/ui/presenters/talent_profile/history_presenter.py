import logging
from PyQt6.QtCore import QObject, pyqtSlot

from data.game_state import Talent

logger = logging.getLogger(__name__)

class HistoryPresenter(QObject):
    """
    Sub-presenter responsible for the HistoryWidget.
    Handles fetching scene history and navigation to scene details.
    """
    def __init__(self, controller, widget, uimanager, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.widget = widget
        self.uimanager = uimanager
        self._connect_signals()

    def _connect_signals(self):
        """Connects widget signals to navigation logic."""
        self.widget.open_scene_dialog_requested.connect(self._on_scene_requested)

    def set_talent(self, talent: Talent):
        """Fetches history from controller and updates the widget."""
        if not talent:
            return
            
        history = self.controller.get_scene_history_for_talent(talent.id)
        self.widget.display_scene_history(history, talent.id)

    @pyqtSlot(int)
    def _on_scene_requested(self, scene_id: int):
        """Handles double-click on a scene item."""
        if scene := self.controller.get_scene_by_id(scene_id):
            self.uimanager.show_shot_scene_details(scene.id)
        else:
            logger.warning(f"Could not find scene with ID {scene_id} to show details.")