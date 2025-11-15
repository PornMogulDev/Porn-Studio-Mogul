from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal
from PyQt6.QtWidgets import QMessageBox

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ui.panels.talent_filter_panel import TalentFilterPanel
    from core.interfaces import IGameController
from data.settings_manager import SettingsManager

class TalentFilterPanelPresenter(QObject):
    """
    Presenter for the TalentFilterPanel. Manages the panel's state,
    including presets, live unit conversion, and all user actions.
    This is the "brain" of the operation.
    """
    # This is the public signal that other parts of the application
    # (like a dashboard coordinator) will connect to.
    filters_applied = pyqtSignal(dict)

    def __init__(self, view: 'TalentFilterPanel', controller: 'IGameController', settings_manager: 'SettingsManager', parent=None):
        super().__init__(parent)
        self.controller = controller
        self.view = view
        self.settings_manager = settings_manager
        
        # Track current role selection
        self.current_scene_id = None
        self.current_vp_id = None

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
            'locations': [],
            'scene_id': None,
            'vp_id': None,
        }

        self._connect_signals()

    def load_initial_data(self):
        """
        Commands the view to populate its controls with the initial filter state,
        loads available scenes, and loads presets. This should be called once
        after the presenter is created.
        """
        self._reload_scenes()
        self.view.load_filters(self.default_filters)
        self._update_presets_in_view()

    @pyqtSlot()
    def _reload_scenes(self):
        """Reloads the list of castable scenes from the controller."""
        scenes = self.controller.get_castable_scenes()
        self.view.populate_scenes(scenes)

    def _connect_signals(self):
        """Connects signals from the view to the presenter's slots."""
        self.view.apply_requested.connect(self.on_apply_requested)
        self.view.reset_requested.connect(self.on_reset_requested)
        self.view.go_to_toggled.connect(self.on_go_to_toggled)
        self.view.load_preset_requested.connect(self.on_load_preset)
        self.view.save_preset_requested.connect(self.on_save_preset)
        self.view.delete_preset_requested.connect(self.on_delete_preset)
        self.view.scene_selected.connect(self._on_scene_selected)
        self.view.role_selected.connect(self._on_role_selected)
        self.settings_manager.signals.setting_changed.connect(self._on_setting_changed)
        self.controller.signals.scenes_changed.connect(self._reload_scenes)

    @pyqtSlot(int)
    def _on_scene_selected(self, scene_id: int):
        self.current_scene_id = scene_id
        if scene_id is not None and scene_id > -1:
            roles = self.controller.get_uncast_roles_for_scene(scene_id)
            self.view.populate_roles(roles)
        else:
            self.current_scene_id = None
            self.current_vp_id = None
            self.view.populate_roles([])
            self.view.set_gender_filter_enabled(True)
            self.view.set_ethnicity_filter_enabled(True)
            self.view.set_physical_filters_for_gender('Any')

    @pyqtSlot(int, int)
    def _on_role_selected(self, scene_id: int, vp_id: int):
        self.current_vp_id = vp_id
        if vp_id is not None and vp_id > -1:
            role_details = self.controller.get_role_details_for_ui(scene_id, vp_id)
            self.view.set_gender_filter_enabled(False)
            self.view.set_ethnicity_filter_enabled(False)
            self.view.set_physical_filters_for_gender(role_details.get('gender', 'Any'))
        else:
            self.current_vp_id = None
            self.view.set_gender_filter_enabled(True)
            self.view.set_ethnicity_filter_enabled(True)
            self.view.set_physical_filters_for_gender('Any')

    @pyqtSlot()
    def on_apply_requested(self):
        current_filters = self.view.gather_current_filters()
        self.filters_applied.emit(current_filters)

    @pyqtSlot()
    def on_reset_requested(self):
        self.view.load_filters(self.default_filters)
        self.view.populate_scenes(self.controller.get_castable_scenes())
        self.view.populate_roles([])
        self.view.set_gender_filter_enabled(True)
        self.view.set_ethnicity_filter_enabled(True)
        self.view.set_physical_filters_for_gender('Any')
        # Also emit the reset filters immediately
        self.filters_applied.emit(self.default_filters)

    @pyqtSlot(bool)
    def on_go_to_toggled(self, is_checked: bool):
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
        presets = self.settings_manager.get_talent_filter_presets()
        self.view.populate_presets(list(presets.keys()), select_text)

    @pyqtSlot(str)
    def _on_setting_changed(self, key: str):
        if key == 'unit_system':
            current_filters = self.view.gather_current_filters()
            self.view.update_dick_size_filter_ui()
            self.view.load_filters(current_filters)