from PyQt6.QtCore import QObject, pyqtSlot

# Forward reference for type hinting
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ui.dialogs.talent_filter_dialog import TalentFilterDialog

class TalentFilterPresenter(QObject):
    """
    Presenter for the TalentFilterDialog. Manages the dialog's state,
    including the initial filters for the "Reset" functionality, and
    handles all user actions.
    """
    def __init__(self, view: 'TalentFilterDialog', initial_filters: dict):
        super().__init__()
        self.view = view
        
        # Capture a snapshot of the filters as they were when the dialog was opened.
        # This is the key to the "Reset" functionality.
        self.initial_filters = initial_filters.copy()

        self._connect_signals()

    def load_initial_data(self):
        """
        Commands the view to populate its controls with the initial filter state.
        This is called once by the view upon its own initialization.
        """
        self.view.load_filters(self.initial_filters)

    def _connect_signals(self):
        """Connects signals from the view to the presenter's slots."""
        self.view.apply_requested.connect(self.on_apply_requested)
        self.view.reset_requested.connect(self.on_reset_requested)
        self.view.apply_and_close_requested.connect(self.on_apply_and_close_requested)
        self.view.go_to_toggled.connect(self.on_go_to_toggled)
    
    @pyqtSlot()
    def on_apply_requested(self):
        """
        Gathers the current filter state from the view and commands the view
        to emit its public `filters_applied` signal.
        """
        current_filters = self.view.gather_current_filters()
        # The view owns the public signal, but the presenter commands when to fire it.
        self.view.filters_applied.emit(current_filters)

    @pyqtSlot()
    def on_reset_requested(self):
        """
        Commands the view to reset its controls to the presenter's stored
        initial state.
        """
        self.view.load_filters(self.initial_filters)
    
    @pyqtSlot()
    def on_apply_and_close_requested(self):
        """
        First, applies the current filters, then commands the view to close
        with an 'Accepted' result.
        """
        self.on_apply_requested()
        self.view.accept()

    @pyqtSlot(bool)
    def on_go_to_toggled(self, is_checked: bool):
        """
        Commands the view to update the enabled state of the category combo box.
        """
        self.view.set_category_combo_enabled(is_checked)