from typing import Union, Tuple, TYPE_CHECKING
from PyQt6.QtCore import QObject, pyqtSlot, Qt, QPoint
from PyQt6.QtWidgets import QDialog

from core.interfaces import IGameController
from ui.tabs.talent_tab import HireWindow
from ui.dialogs.talent_filter_dialog import TalentFilterDialog
from data.game_state import Talent
from ui.windows.talent_profile_window import TalentProfileWindow
from ui.dialogs.scene_dialog import SceneDialog
from utils.formatters import get_fuzzed_skill_range

if TYPE_CHECKING:
    from ui.ui_manager import UIManager

class TalentTabPresenter(QObject):
    def __init__(self, controller: IGameController, view: HireWindow, ui_manager: 'UIManager'):
        super().__init__()
        self.controller = controller
        self.view = view
        self.ui_manager = ui_manager
        self.filter_dialog = None
        self._connect_signals()
        self.view.create_model_and_load(
            self.controller.settings_manager,
            self.controller.get_available_boob_cups()
        )
    def _connect_signals(self):
        self.controller.signals.talent_pool_changed.connect(self.view.refresh_from_state)
        self.controller.signals.go_to_categories_changed.connect(self.view.refresh_from_state)
        self.controller.signals.go_to_list_changed.connect(self.view.refresh_from_state)

        self.view.initial_load_requested.connect(self.on_initial_load)
        self.view.standard_filters_changed.connect(self.on_standard_filters_changed)
        self.view.context_menu_requested.connect(self.on_context_menu_requested)
        self.view.add_talent_to_category_requested.connect(self.controller.add_talent_to_go_to_category)
        self.view.remove_talent_from_category_requested.connect(self.controller.remove_talent_from_go_to_category)
        self.view.open_advanced_filters_requested.connect(self.on_open_advanced_filters)
        self.view.open_talent_profile_requested.connect(self.on_open_talent_profile)
        self.view.help_requested.connect(self.on_help_requested)

    @pyqtSlot()
    def on_initial_load(self):
        self.view.refresh_from_state()

    def _talent_passes_skill_filters(self, talent: Talent, skill_filters: dict) -> bool:
        """Checks if a talent's fuzzed skill ranges overlap with user's filter ranges."""
        
        skill_checks = {
            'performance': ('performance_min', 'performance_max'),
            'acting': ('acting_min', 'acting_max'),
            'stamina': ('stamina_min', 'stamina_max'),
        }

        for skill_attr, (min_key, max_key) in skill_checks.items():
            user_min = skill_filters.get(min_key)
            user_max = skill_filters.get(max_key)
            
            if user_min is None or user_max is None: continue

            true_skill_val = getattr(talent, skill_attr, 0.0)
            fuzzed_range: Union[int, Tuple[int, int]] = get_fuzzed_skill_range(true_skill_val, talent.experience, talent.id)
            
            if isinstance(fuzzed_range, int):
                if not (user_min <= fuzzed_range <= user_max): return False
            else:
                talent_min, talent_max = fuzzed_range
                if not (talent_min <= user_max and talent_max >= user_min): return False
                    
        return True

    @pyqtSlot(dict)
    def on_standard_filters_changed(self, all_filters: dict):
        filters_for_db = all_filters.copy()
        skill_filter_keys = ['performance_min', 'performance_max', 'acting_min', 'acting_max', 'stamina_min', 'stamina_max']
        for key in skill_filter_keys:
            filters_for_db.pop(key, None)

        role_filter = all_filters.get('role_filter', {'active': False})

        if role_filter.get('active') and role_filter.get('filter_by_reqs'):
            role_details = self.controller.hire_talent_service.get_role_details_for_ui(
                role_filter['scene_id'], role_filter['vp_id']
            )
            filters_for_db['gender'] = role_details.get('gender')
            if ethnicity := role_details.get('ethnicity', "Any"):
                if ethnicity != "Any": filters_for_db['ethnicities'] = [ethnicity]
            self.view.set_standard_filters_enabled(False) # Disable advanced filter button
        else:
            self.view.set_standard_filters_enabled(True)

        talents_from_db = self.controller.get_filtered_talents(filters_for_db)
        
        talents_passing_skills = [
            t for t in talents_from_db 
            if self._talent_passes_skill_filters(t.to_dataclass(Talent), all_filters)
        ]

        if role_filter.get('active') and role_filter.get('hide_refusals'):
            final_talents = self.controller.hire_talent_service.filter_talents_by_availability(talents_passing_skills, role_filter['scene_id'], role_filter['vp_id'])
        else:
            final_talents = talents_passing_skills
            
        self.view.update_talent_list(final_talents)
    
    @pyqtSlot(object, QPoint)
    def on_context_menu_requested(self, talent: Talent, pos: QPoint):
        all_categories = self.controller.get_go_to_list_categories()
        talent_categories = self.controller.get_talent_go_to_categories(talent.id)
        self.view.display_talent_context_menu(talent, all_categories, talent_categories, pos)

    @pyqtSlot(dict)
    def on_open_advanced_filters(self, current_filters: dict):
        if self.filter_dialog is None:
            # Create the dialog for the first time
            self.filter_dialog = TalentFilterDialog(
                ethnicities=self.controller.get_available_ethnicities(),
                boob_cups=self.controller.get_available_boob_cups(),
                go_to_categories=self.controller.get_go_to_list_categories(),
                current_filters=current_filters,
                settings_manager=self.controller.settings_manager,
                parent=self.view
            )
            self.filter_dialog.filters_applied.connect(self.view.on_filters_applied)
            # When the user closes the dialog via the 'X' button, clear our reference to it
            self.filter_dialog.finished.connect(self.on_filter_dialog_closed)
            self.filter_dialog.show()
        else:
            # If it already exists, just bring it to the front
            self.filter_dialog.raise_()
            self.filter_dialog.activateWindow()
     
    def on_filter_dialog_closed(self):
        self.filter_dialog = None
    
    @pyqtSlot(object)
    def on_open_talent_profile(self, talent: Talent):
        """Handles the request to open a talent's profile, delegating to the UIManager."""
        self.ui_manager.show_talent_profile(talent)

    @pyqtSlot(str)
    def on_help_requested(self, topic_key: str):
        self.ui_manager.show_help(topic_key)