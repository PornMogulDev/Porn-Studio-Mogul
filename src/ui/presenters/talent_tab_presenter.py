from typing import List, Dict, TYPE_CHECKING
from PyQt6.QtCore import QObject, pyqtSlot, Qt, QPoint
from PyQt6.QtWidgets import QDialog

from core.interfaces import IGameController
from ui.tabs.talent_tab import HireWindow
from ui.dialogs.talent_filter_dialog import TalentFilterDialog
from data.game_state import Talent
from ui.dialogs.talent_profile_dialog import TalentProfileDialog
from ui.dialogs.scene_dialog import SceneDialog

if TYPE_CHECKING:
    from ui.ui_manager import UIManager

class TalentTabPresenter(QObject):
    def __init__(self, controller: IGameController, view: HireWindow, ui_manager: 'UIManager'):
        super().__init__()
        self.controller = controller
        self.view = view
        self.ui_manager = ui_manager
        self._connect_signals()
        self.view.initial_load_requested.emit()
    def _connect_signals(self):
        self.controller.signals.scenes_changed.connect(self.on_global_scenes_changed)
        self.controller.signals.talent_pool_changed.connect(self.view.refresh_from_state)
        self.controller.signals.go_to_categories_changed.connect(self.view.refresh_from_state)
        self.controller.signals.go_to_list_changed.connect(self.view.refresh_from_state)

        self.view.initial_load_requested.connect(self.on_initial_load)
        self.view.scene_filter_selected.connect(self.on_scene_selected_for_filter)
        self.view.show_role_info_requested.connect(self.on_show_role_info)
        self.view.clear_role_info_requested.connect(self.on_clear_role_info)
        self.view.standard_filters_changed.connect(self.on_standard_filters_changed)
        self.view.context_menu_requested.connect(self.on_context_menu_requested)
        self.view.add_talent_to_category_requested.connect(self.controller.add_talent_to_go_to_category)
        self.view.remove_talent_from_category_requested.connect(self.controller.remove_talent_from_go_to_category)
        self.view.open_advanced_filters_requested.connect(self.on_open_advanced_filters)
        self.view.open_talent_profile_requested.connect(self.on_open_talent_profile)
        self.view.help_requested.connect(self.on_help_requested)

    @pyqtSlot()
    def on_global_scenes_changed(self):
        castable_scenes = self.controller.get_castable_scenes()
        self.view.update_scene_dropdown(castable_scenes)

    @pyqtSlot()
    def on_initial_load(self):
        self.on_global_scenes_changed()
        self.view.refresh_from_state()

    @pyqtSlot(int)
    def on_scene_selected_for_filter(self, scene_id: int):
        roles = self.controller.get_uncast_roles_for_scene(scene_id) if scene_id > 0 else []
        self.view.update_role_dropdown(roles)

    @pyqtSlot(int, int)
    def on_show_role_info(self, scene_id: int, vp_id: int):
        role_details = self.controller.hire_talent_service.get_role_details_for_ui(scene_id, vp_id)
        html = "<ul>"
        html += f"<li><b>Gender:</b> {role_details.get('gender', 'N/A')}</li>"
        html += f"<li><b>Ethnicity:</b> {role_details.get('ethnicity', 'N/A')}</li>"
        if role_details.get('is_protagonist'): html += "<li><b>Protagonist Role</b></li>"
        if role_details.get('disposition') != 'Switch': html += f"<li><b>Disposition:</b> {role_details.get('disposition', 'N/A')}</li>"

        if physical_tags := role_details.get('physical_tags'): html += f"<br><li><b>Physical Tags:</b><br>{', '.join(physical_tags)}</li>"
        if action_roles := role_details.get('action_roles'): html += f"<br><li><b>Action Roles:</b><br>{', '.join(action_roles)}</li>"
        html += "</ul>"
        
        self.view.display_role_info(html)
        self.view.set_standard_filters_enabled(False)
        
        # Filter the list to only show eligible talent
        eligible_talent_list = self.controller.hire_talent_service.get_eligible_talent_for_role(scene_id, vp_id)
        self.view.update_talent_list(eligible_talent_list)

    @pyqtSlot()
    def on_clear_role_info(self):
        self.view.clear_role_info()
        self.view.set_standard_filters_enabled(True)
        self.view.refresh_from_state()

    @pyqtSlot(dict)
    def on_standard_filters_changed(self, all_filters: dict):
        filtered_talents = self.controller.get_filtered_talents(all_filters)
        self.view.update_talent_list(filtered_talents)
    
    @pyqtSlot(object, QPoint)
    def on_context_menu_requested(self, talent: Talent, pos: QPoint):
        all_categories = self.controller.get_go_to_list_categories()
        talent_categories = self.controller.get_talent_go_to_categories(talent.id)
        self.view.display_talent_context_menu(talent, all_categories, talent_categories, pos)

    @pyqtSlot(dict)
    def on_open_advanced_filters(self, current_filters: dict):
        dialog = TalentFilterDialog(
            ethnicities=self.controller.get_available_ethnicities(),
            boob_cups=self.controller.get_available_boob_cups(),
            go_to_categories=self.controller.get_go_to_list_categories(),
            current_filters=current_filters,
            settings_manager=self.controller.settings_manager,
            parent=self.view
        )
        dialog.filters_applied.connect(self.view.on_filters_applied)
        # Ensure the dialog is destroyed on close, preventing resource leaks.
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.exec()
    
    @pyqtSlot(object)
    def on_open_talent_profile(self, talent: Talent):
        """Handles the request to open a talent's profile, delegating to the UIManager."""
        self.ui_manager.show_talent_profile(talent)

    @pyqtSlot(str)
    def on_help_requested(self, topic_key: str):
        self.ui_manager.show_help(topic_key)