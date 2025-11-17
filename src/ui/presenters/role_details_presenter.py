import logging
from typing import TYPE_CHECKING
from PyQt6.QtCore import QObject

from ui.builders.role_details_builder import prepare_role_details_data, format_role_details_html

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
        NOW USES THE BUILDER.
        """
        details_data = prepare_role_details_data(scene_id, vp_id, self.controller)
        
        if not details_data:
            self.clear()
            return
            
        html = format_role_details_html(details_data)
        self.view.update_role_details(html)

    def get_role_details_as_html(self, scene_id: int, vp_id: int) -> str:
        """
        Returns the formatted HTML for a role without updating a view.
        This is a new helper method for our tooltip use case.
        """
        details_data = prepare_role_details_data(scene_id, vp_id, self.controller)
        return format_role_details_html(details_data)

    def clear(self):
        """
        Instructs the view to clear its display and show the default message.
        """
        self.view.clear()