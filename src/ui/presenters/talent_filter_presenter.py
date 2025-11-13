from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QMessageBox

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ui.dialogs.talent_filter_dialog import TalentFilterDialog
from data.settings_manager import SettingsManager

class TalentFilterPresenter(QObject):
    """
    Presenter for the TalentFilterDialog. Manages the dialog's state,
    including presets, live unit conversion, and all user actions.
    This is the "brain" of the operation.
    """
    def __init__(self, view: 'TalentFilterDialog', initial_filters: dict, settings_manager: 'SettingsManager'):
        super().__init__()
        self.view = view
        self.settings_manager = settings_manager

        # Capture a snapshot of the filters as they were when the dialog was opened.
        self.initial_filters = initial_filters.copy()

        # Define a hardcoded "factory default" state for the reset functionality.
        self.default_filters = {
            'go_to_list_only': False,
            'go_to_category_id': -1,
            'gender': 'Any',
            'age_min': 18, 'age_max': 99,
            'performance_min': 0, 'performance_max': 100,
            'acting_min': 0, 'acting_max': 100,
            'stamina_min': 0, 'stamina_max': 100,
            'dominance_min': 0, 'dominance_max': 100,
            'submission_min': 0, 'submission_max': 100,
            'dick_size_min': 0, 'dick_size_max': 20,
            'ethnicities': [],
            'cup_sizes': [],
            'nationalities': [],
            'locations': []
        }

        self._connect_signals()

    def load_initial_data(self):
        """
        Commands the view to populate its controls with the initial filter state
        and loads the available presets.
        """
        self.view.load_filters(self.initial_filters)
        self._update_presets_in_view()

    def _connect_signals(self):
        """Connects signals from the view to the presenter's slots."""
        self.view.apply_requested.connect(self.on_apply_requested)
        self.view.reset_requested.connect(self.on_reset_requested)
        self.view.apply_and_close_requested.connect(self.on_apply_and_close_requested)
        self.view.go_to_toggled.connect(self.on_go_to_toggled)
        
        # Connect to preset management signals from the view
        self.view.load_preset_requested.connect(self.on_load_preset)
        self.view.save_preset_requested.connect(self.on_save_preset)
        self.view.delete_preset_requested.connect(self.on_delete_preset)
        
        # Listen for global settings changes
        self.settings_manager.signals.setting_changed.connect(self._on_setting_changed)

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
        default (factory) state.
        """
        self.view.load_filters(self.default_filters)

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
        
    @pyqtSlot()
    def on_load_preset(self):
        preset_name = self.view.preset_combo.currentText()
        if not preset_name:
            return
        presets = self.settings_manager.get_talent_filter_presets()
        preset_data = presets.get(preset_name)
        if preset_data:
            self.view.load_filters(preset_data)
        else:
            QMessageBox.warning(self.view, "Load Error", f"Could not find preset named '{preset_name}'.")

    @pyqtSlot()
    def on_save_preset(self):
        preset_name = self.view.preset_combo.currentText()
        if not preset_name:
            QMessageBox.warning(self.view, "Save Preset", "Please enter a name for the preset.")
            return
        current_filters = self.view.gather_current_filters()
        presets = self.settings_manager.get_talent_filter_presets()
        presets[preset_name] = current_filters
        self.settings_manager.set_talent_filter_presets(presets)
        self._update_presets_in_view(select_text=preset_name)
        QMessageBox.information(self.view, "Preset Saved", f"Preset '{preset_name}' has been saved.")

    @pyqtSlot()
    def on_delete_preset(self):
        preset_name = self.view.preset_combo.currentText()
        if not preset_name:
            return
        reply = QMessageBox.question(self.view, "Delete Preset", f"Are you sure you want to delete the preset '{preset_name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            presets = self.settings_manager.get_talent_filter_presets()
            if preset_name in presets:
                del presets[preset_name]
                self.settings_manager.set_talent_filter_presets(presets)
                self._update_presets_in_view()

    def _update_presets_in_view(self, select_text: str = None):
        """Gets presets from the model and commands the view to update its list."""
        presets = self.settings_manager.get_talent_filter_presets()
        self.view.populate_presets(list(presets.keys()), select_text)

    @pyqtSlot(str)
    def _on_setting_changed(self, key: str):
        """Handles live updates if the unit system is changed while the dialog is open."""
        if key == 'unit_system':
            # 1. Get current filter values, standardized to inches by the view's gather method
            current_filters = self.view.gather_current_filters()
            # 2. Command the view to update its UI's label and range for the new unit system
            self.view.update_dick_size_filter_ui()
            # 3. Command the view to reload the standardized inch values, which will be converted to the new UI unit
            self.view.load_filters(current_filters)