from PyQt6.QtCore import QObject, pyqtSignal, QPoint, pyqtSlot
from typing import TYPE_CHECKING, List, Dict

from core.interfaces import IGameController
from data.game_state import Talent

if TYPE_CHECKING:
    from ui.widgets.hiring_dashboard.talent_table_widget import TalentTableWidget

class TalentTablePresenter(QObject):
    """
    Presenter for the TalentTableWidget.
    This presenter manages the talent table in the hiring dashboard. It's
    designed to be coordinated by a parent presenter (e.g., a dashboard
    presenter or UI coordinator). It does not perform filtering itself but
    emits signals when filter criteria change and accepts filtered data
    to display.
    """
    # Outbound signals for the coordinator
    open_talent_profile_requested = pyqtSignal(object)
    filters_changed = pyqtSignal()

    def __init__(self, controller: IGameController, view: 'TalentTableWidget', parent=None):
        super().__init__(parent)
        self.controller = controller
        self.view = view

        self._initialize_view()
        self._connect_signals()

    def _initialize_view(self):
        """Initializes the view with necessary data from the controller."""
        self.view.initialize_model(
            self.controller.settings_manager,
            self.controller.get_available_cup_sizes()
        )

    def _connect_signals(self):
        """Connects signals between the view, controller, and this presenter."""
        # View signals that trigger a coordinator action
        self.view.name_filter_changed.connect(self.filters_changed.emit)
        self.view.open_talent_profile_requested.connect(self.open_talent_profile_requested.emit)

        # View signals handled by this presenter
        self.view.context_menu_requested.connect(self._on_context_menu_requested)

        # View signals that map directly to controller commands
        self.view.add_talent_to_category_requested.connect(self.controller.add_talents_to_go_to_category)
        self.view.remove_talent_from_category_requested.connect(self.controller.remove_talents_from_go_to_category)

    @pyqtSlot(list, QPoint)
    def _on_context_menu_requested(self, talents: List[Talent], pos: QPoint):
        """
        Fetches Go-To categories and instructs the view to display the context menu.
        """
        all_categories = self.controller.get_go_to_list_categories()
        self.view.display_talent_context_menu(talents, all_categories, pos)

    # --- Public API for the Coordinator ---

    def update_data(self, talent_data: List[Dict]):
        """
        Public method for the coordinator to push filtered talent data into the view.
        """
        self.view.update_talent_table(talent_data)

    def get_name_filter(self) -> str:
        """
        Public method for the coordinator to retrieve the current name filter value.
        """
        return self.view.get_name_filter()