from typing import Dict
from PyQt6.QtCore import QObject, pyqtSlot

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ui.dialogs.talent_filter_dialog import TalentFilterDialog
    from core.interfaces import IGameController
from data.settings_manager import SettingsManager
from utils.preset_handler import PresetHandler

class TalentFilterPresenter(QObject):
    def __init__(self, view: 'TalentFilterDialog', controller: 'IGameController', initial_filters: dict, settings_manager: 'SettingsManager'):
        super().__init__()
        self.controller = controller
        self.view = view
        self.settings_manager = settings_manager

        self.initial_filters = initial_filters.copy()

        self.default_filters = {
            'go_to_list_only': False, 'go_to_category_id': -1, 'gender': 'Any',
            'age_min': 18, 'age_max': 99, 'performance_min': 0, 'performance_max': 100,
            'acting_min': 0, 'acting_max': 100, 'stamina_min': 0, 'stamina_max': 100,
            'dominance_min': 0, 'dominance_max': 100, 'submission_min': 0, 'submission_max': 100,
            'dick_size_min': 0, 'dick_size_max': 20, 'ethnicities': [], 'cup_sizes': [],
            'nationalities': [], 'locations': [], 'effective_locations': [], 'scene_id': None, 'vp_id': None,
        }
        self._connect_signals()

        # --- Initialize Preset Handler ---
        self.preset_handler = PresetHandler(
            widget=self.view.preset_widget,
            settings_manager=self.settings_manager,
            settings_key="talent_filter_presets",
            parent_view=self.view,
            save_callback=self._get_filters_for_preset,
            load_callback=self._apply_preset_filters
        )

    def load_initial_data(self):
        self._reload_scenes()
        self.view.load_filters(self.initial_filters) # Load previous filters first

    @pyqtSlot()
    def _reload_scenes(self):
        scenes = self.controller.get_castable_scenes()
        self.view.populate_scenes(scenes)
        self.view.populate_roles([])

    def _connect_signals(self):
        self.view.apply_requested.connect(self.on_apply_requested)
        self.view.reset_requested.connect(self.on_reset_requested)
        self.view.go_to_toggled.connect(self.on_go_to_toggled)
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
            self.current_scene_id = None; self.current_vp_id = None
            self.view.populate_roles([])
            self.view.set_gender_filter_enabled(True); self.view.set_ethnicity_filter_enabled(True)
            self.view.set_physical_filters_for_gender('Any')

    @pyqtSlot(int, int)
    def _on_role_selected(self, scene_id: int, vp_id: int):
        self.current_vp_id = vp_id
        if vp_id is not None and vp_id > -1:
            role_details = self.controller.get_role_details_for_ui(scene_id, vp_id)
            self.view.set_gender_filter_enabled(False); self.view.set_ethnicity_filter_enabled(False)
            self.view.set_physical_filters_for_gender(role_details.get('gender', 'Any'))
        else:
            self.current_vp_id = None
            self.view.set_gender_filter_enabled(True); self.view.set_ethnicity_filter_enabled(True)
            self.view.set_physical_filters_for_gender('Any')

    @pyqtSlot()
    def on_apply_requested(self):
        self.view.filters_applied.emit(self.view.gather_current_filters())

    @pyqtSlot()
    def on_reset_requested(self):
        self.view.load_filters(self.default_filters)
        self.view.populate_scenes(self.controller.get_castable_scenes())
        self.view.populate_roles([])
        self.view.set_gender_filter_enabled(True); self.view.set_ethnicity_filter_enabled(True)
        self.view.set_physical_filters_for_gender('Any')
        self.on_apply_requested() # Immediately apply the reset filters

    @pyqtSlot(bool)
    def on_go_to_toggled(self, is_checked: bool):
        self.view.set_category_combo_enabled(is_checked)

    # --- Preset Handler Callbacks ---

    def _get_filters_for_preset(self) -> Dict:
        """Callback for PresetHandler to get data to save."""
        return self.view.gather_current_filters()
    
    def _apply_preset_filters(self, preset_data: Dict):
        """Callback for PresetHandler to apply loaded data."""
        self.view.load_filters(preset_data)

    @pyqtSlot(str)
    def _on_setting_changed(self, key: str):
        if key == 'unit_system':
            current_filters = self.view.gather_current_filters()
            self.view.update_dick_size_filter_ui()
            self.view.load_filters(current_filters)