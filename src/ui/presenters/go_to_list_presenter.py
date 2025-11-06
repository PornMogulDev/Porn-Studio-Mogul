import logging
from PyQt6.QtCore import QObject

from core.interfaces import IGameController

# Sentinel value for the "All Talents" view, to be shared with the view
ALL_TALENTS_ID = -1

logger = logging.getLogger(__name__)

class GoToListPresenter(QObject):
    """
    Manages the state and logic for the GoToTalentDialog.
    """
    def __init__(self, controller: IGameController, view, ui_manager, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.view = view
        self.ui_manager = ui_manager

        # --- Internal State ---
        self._current_category_id: int | None = None
        self._all_categories: list[dict] = []

    # --- Lifecycle and Initialization ---
    def initialize(self):
        """Called by the view after it's been constructed."""
        self._connect_signals()
        self._refresh_categories_and_update_view()
        # Set initial selection to "All Talents"
        self.select_category(ALL_TALENTS_ID)

    def _connect_signals(self):
        self.controller.signals.go_to_categories_changed.connect(self._on_categories_changed)
        self.controller.signals.go_to_list_changed.connect(self._on_list_assignments_changed)

    def disconnect_signals(self):
        """Disconnects from global signals to prevent memory leaks."""
        try:
            self.controller.signals.go_to_categories_changed.disconnect(self._on_categories_changed)
            self.controller.signals.go_to_list_changed.disconnect(self._on_list_assignments_changed)
            logger.debug("GoToListPresenter signals disconnected.")
        except TypeError:
            logger.warning("Attempted to disconnect GoToListPresenter signals that were not connected.")

    # --- Signal Handlers ---
    def _on_categories_changed(self):
        self._refresh_categories_and_update_view()

    def _on_list_assignments_changed(self):
        # Just refresh the talent list for the currently selected category
        if self._current_category_id is not None:
            self.select_category(self._current_category_id)

    # --- Data and Logic Methods ---
    def _refresh_categories_and_update_view(self):
        """Fetches latest categories and tells the view to update."""
        self._all_categories = self.controller.get_go_to_list_categories()
        
        # Ensure the current selection is still valid
        if self._current_category_id not in [cat['id'] for cat in self._all_categories] and self._current_category_id != ALL_TALENTS_ID:
            self._current_category_id = ALL_TALENTS_ID # Fallback to "All"

        self.view.display_categories(self._all_categories, self._current_category_id)

    def select_category(self, category_id: int | None):
        """
        Main logic driver. Called when the user selects a category in the view.
        Fetches and displays talents for the given category.
        """
        if category_id is None:
            self._current_category_id = None
            self.view.display_talents([])
            self._update_view_button_states()
            return
        
        self._current_category_id = category_id
        
        talents = []
        if category_id == ALL_TALENTS_ID:
            talents = self.controller.get_go_to_list_talents()
        else:
            talents = self.controller.get_talents_in_go_to_category(category_id)

        sorted_talents = sorted(talents, key=lambda t: t.alias)
        self.view.display_talents(sorted_talents)
        self._update_view_button_states()

    def _update_view_button_states(self):
        """Calculates button states and tells the view to apply them."""
        is_real_category, is_deletable = False, False
        
        if self._current_category_id is not None and self._current_category_id != ALL_TALENTS_ID:
            current_cat_data = next((cat for cat in self._all_categories if cat['id'] == self._current_category_id), None)
            if current_cat_data:
                is_real_category = True
                is_deletable = current_cat_data.get('is_deletable', False)

        button_states = {
            'remove_enabled': is_real_category,
            'rename_enabled': is_real_category,
            'delete_enabled': is_deletable,
        }
        self.view.update_button_states(button_states)
    
    def get_current_category_info(self) -> dict:
        """Provides info about the currently selected category to the view."""
        if self._current_category_id is not None and self._current_category_id != ALL_TALENTS_ID:
            return next((cat for cat in self._all_categories if cat['id'] == self._current_category_id), {})
        return {}

    def get_context_menu_model(self) -> dict:
        """Builds a simple data structure for the view to render the context menu."""
        # Use the cached category list for performance
        sorted_cats = sorted(self._all_categories, key=lambda c: c['name'])
        
        # Model: a list of dictionaries. The view just iterates and creates actions.
        add_to_model = [{'id': cat['id'], 'name': cat['name']} for cat in sorted_cats]
        remove_from_model = [{'id': cat['id'], 'name': cat['name']} for cat in sorted_cats]

        return {
            'add_to': add_to_model,
            'remove_from': remove_from_model,
        }

    # --- Actions (Called by the View) ---
    def create_category(self, name: str):
        self.controller.create_go_to_list_category(name)

    def rename_current_category(self, new_name: str):
        if self._current_category_id is not None and self._current_category_id != ALL_TALENTS_ID:
            self.controller.rename_go_to_list_category(self._current_category_id, new_name)

    def delete_current_category(self):
        if self._current_category_id is not None and self._current_category_id != ALL_TALENTS_ID:
            self.controller.delete_go_to_list_category(self._current_category_id)
    
    def remove_talents_from_current_category(self, talent_ids: list[int]):
        """Action for the 'Remove from Category' button."""
        if self._current_category_id is not None and self._current_category_id != ALL_TALENTS_ID:
            if talent_ids:
                self.controller.remove_talents_from_go_to_category(talent_ids, self._current_category_id)

    def add_talents_to_category(self, talent_ids: list[int], category_id: int):
        """Action for the context menu 'Add to...'."""
        self.controller.add_talents_to_go_to_category(talent_ids, category_id)

    def remove_talents_from_category(self, talent_ids: list[int], category_id: int):
        """Action for the context menu 'Remove from...'."""
        self.controller.remove_talents_from_go_to_category(talent_ids, category_id)

    def show_talent_profile(self, talent):
        self.ui_manager.show_talent_profile(talent)