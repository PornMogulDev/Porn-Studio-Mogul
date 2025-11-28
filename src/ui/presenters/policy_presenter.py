import logging
from PyQt6.QtCore import QObject

logger = logging.getLogger(__name__)

class PolicyPresenter(QObject):
    def __init__(self, controller, view, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.view = view
        
    def initialize(self):
        """
        Loads definitions and active state, then updates view.
        """
        # Load from the renamed data attribute
        policy_data = getattr(self.controller.data_manager, "studio_policies_data", {})
        
        if isinstance(policy_data, dict):
            definitions = list(policy_data.values())
        else:
            definitions = policy_data

        active_ids = self.controller.game_state.studio.studio_policies
        
        self.view.display_policies(definitions, active_ids)

    def on_policy_toggled(self, policy_id: str, is_checked: bool):
        """
        Updates the GameState and DB immediately when a checkbox is toggled.
        """
        self.controller.toggle_studio_policy(policy_id, is_checked)