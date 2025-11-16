import logging
from typing import TYPE_CHECKING
from PyQt6.QtCore import QObject

if TYPE_CHECKING:
    from core.interfaces import IGameController
    from ui.widgets.role_details_widget import RoleDetailsWidget

logger = logging.getLogger(__name__)

class RoleDetailsPresenter(QObject):
    """
    Presenter for the RoleDetailsWidget.
    This presenter is responsible for fetching role-specific data from the
    controller, formatting it for display, and instructing its associated
    view to render it. It keeps display logic out of the coordinator presenter.
    """
    def __init__(self, controller: 'IGameController', view: 'RoleDetailsWidget', parent=None):
        super().__init__(parent)
        self.controller = controller
        self.view = view

    def display_role(self, scene_id: int, vp_id: int):
        """
        Fetches details for a specific role and updates the view.
        """
        if not scene_id or not vp_id:
            self.clear()
            return

        role_details = self.controller.get_role_details_for_ui(scene_id, vp_id)
        if not role_details:
            logger.warning(f"Could not fetch role details for scene {scene_id}, vp {vp_id}")
            self.clear()
            return
            
        # Format the details into an HTML string
        html = "<ul>"
        html += f"<li><b>Gender:</b> {role_details.get('gender', 'N/A')}</li>"
        html += f"<li><b>Ethnicity:</b> {role_details.get('ethnicity', 'N/A')}</li>"
        
        if role_details.get('is_protagonist'):
            html += "<li><b>Protagonist Role</b></li>"
            
        if role_details.get('disposition') != 'Switch':
            html += f"<li><b>Disposition:</b> {role_details.get('disposition', 'N/A')}</li>"
            
        if physical_tags := role_details.get('physical_tags'):
            html += f"<br><li><b>Physical Tags:</b><br>{', '.join(physical_tags)}</li>"
            
        if action_roles := role_details.get('action_roles'):
            html += f"<br><li><b>Action Roles:</b><br>{', '.join(action_roles)}</li>"
            
        html += "</ul>"
        
        self.view.update_role_details(html)

    def clear(self):
        """
        Instructs the view to clear its display and show the default message.
        """
        self.view.clear()