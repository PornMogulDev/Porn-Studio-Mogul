from typing import List, Dict
from PyQt6.QtCore import QObject, pyqtSlot, Qt, QPoint
from PyQt6.QtWidgets import QDialog

from interfaces import IGameController
from ui.tabs.talent_tab import HireWindow
from ui.dialogs.talent_filter_dialog import TalentFilterDialog
from game_state import Talent
from ui.dialogs.talent_profile_dialog import TalentProfileDialog
from ui.dialogs.scene_dialog import SceneDialog

class TalentTabPresenter(QObject):
    def __init__(self, controller: IGameController, view: HireWindow):
        super().__init__()
        self.controller = controller
        self.view = view
        self._talent_profile_dialog_singleton = None
        self._open_profile_dialogs_multi = {} 
        self._connect_signals()
        self.view.initial_load_requested.emit()
    def _connect_signals(self):
        self.controller.signals.scenes_changed.connect(self.on_global_scenes_changed)
        self.controller.signals.talent_pool_changed.connect(self.view.refresh_from_state)
        self.controller.settings_manager.signals.setting_changed.connect(self.view.talent_detail_view.on_setting_changed)
        self.controller.signals.go_to_categories_changed.connect(self.view.refresh_from_state)

        self.view.initial_load_requested.connect(self.on_initial_load)
        self.view.scene_filter_selected.connect(self.on_scene_selected_for_filter)
        self.view.role_filter_applied.connect(self.on_role_filter_applied)
        self.view.role_filter_cleared.connect(self.on_role_filter_cleared)
        self.view.standard_filters_changed.connect(self.on_standard_filters_changed)
        self.view.talent_selected.connect(self.on_talent_selected)
        self.view.context_menu_requested.connect(self.on_context_menu_requested)
        self.view.add_talent_to_category_requested.connect(self.controller.add_talent_to_go_to_category)
        self.view.remove_talent_from_category_requested.connect(self.controller.remove_talent_from_go_to_category)
        self.view.open_advanced_filters_requested.connect(self.on_open_advanced_filters)
        self.view.open_talent_profile_requested.connect(self.on_open_talent_profile)
        self.view.open_scene_dialog_requested.connect(self.on_open_scene_dialog)
        self.view.hire_requested.connect(self.on_hire_requested)

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
    def on_role_filter_applied(self, scene_id: int, vp_id: int):
        eligible_talent = self.controller.talent_service.get_eligible_talent_for_role(scene_id, vp_id)
        self.view.update_talent_list(eligible_talent)
        self.view.set_standard_filters_enabled(False)

    @pyqtSlot()
    def on_role_filter_cleared(self):
        self.view.set_standard_filters_enabled(True)
        self.view.refresh_from_state()

    @pyqtSlot(dict)
    def on_standard_filters_changed(self, all_filters: dict):
        filtered_talents = self.controller.get_filtered_talents(all_filters)
        self.view.update_talent_list(filtered_talents)

    @pyqtSlot(object)
    def on_talent_selected(self, talent: Talent):
        available_roles = self.controller.talent_service.find_available_roles_for_talent(talent.id)
        tag_defs = self.controller.data_manager.tag_definitions
        policy_defs = self.controller.data_manager.on_set_policies_data
        self.view.talent_detail_view.display_talent(talent, available_roles, tag_defs, policy_defs)

    @pyqtSlot(int, list)
    def on_hire_requested(self, talent_id: int, roles: list):
        self.controller.cast_talent_for_multiple_roles(talent_id, roles)
        self.on_global_scenes_changed()
    
    @pyqtSlot(object, QPoint)
    def on_context_menu_requested(self, talent: Talent, pos: QPoint):
        all_categories = self.controller.get_go_to_list_categories()
        talent_categories = self.controller.get_talent_go_to_categories(talent.id)
        self.view.display_talent_context_menu(talent, all_categories, talent_categories, pos)

    @pyqtSlot(dict)
    def on_open_advanced_filters(self, current_filters: dict):
        dialog = self.view.findChild(TalentFilterDialog)
        if dialog: dialog.raise_(); dialog.activateWindow(); return

        categories = self.controller.get_go_to_list_categories()
        dialog = TalentFilterDialog(
            ethnicities=self.controller.get_available_ethnicities(),
            boob_cups=self.controller.get_available_boob_cups(),
            go_to_categories=categories,
            current_filters=current_filters,
            settings_manager=self.controller.settings_manager,
            parent=self.view
        )
        dialog.filters_applied.connect(self.view.on_filters_applied)
        dialog.exec()
    
    @pyqtSlot(object)
    def on_open_talent_profile(self, talent: Talent):
        behavior = self.controller.settings_manager.get_setting("talent_profile_dialog_behavior")
        
        if behavior == 'singleton':
            # --- Singleton Logic ---
            if self._talent_profile_dialog_singleton is None:
                # Create dialog if it doesn't exist
                dialog = TalentProfileDialog(talent, self.controller, self.view)
                dialog.destroyed.connect(self._on_singleton_profile_closed)
                self._talent_profile_dialog_singleton = dialog
                dialog.show()
            else:
                # Update existing dialog
                self._talent_profile_dialog_singleton.update_with_talent(talent)
                self._talent_profile_dialog_singleton.raise_()
                self._talent_profile_dialog_singleton.activateWindow()
        else:
            # --- Multi-instance Logic (Default) ---
            talent_id = talent.id
            if talent_id in self._open_profile_dialogs_multi:
                # Focus existing dialog
                dialog = self._open_profile_dialogs_multi[talent_id]
                dialog.raise_()
                dialog.activateWindow()
            else:
                # Create new dialog
                dialog = TalentProfileDialog(talent, self.controller, self.view)
                # Use a lambda to pass the talent_id for cleanup
                dialog.destroyed.connect(
                    lambda obj=None, t_id=talent_id: self._on_multi_profile_closed(t_id)
                )
                self._open_profile_dialogs_multi[talent_id] = dialog
                dialog.show()

    # Cleanup slots for modeless dialogs
    @pyqtSlot()
    def _on_singleton_profile_closed(self):
        """Clear the reference when the singleton dialog is closed."""
        self._talent_profile_dialog_singleton = None

    @pyqtSlot(int)
    def _on_multi_profile_closed(self, talent_id: int):
        """Remove the specific dialog from the dict when it's closed."""
        if talent_id in self._open_profile_dialogs_multi:
            del self._open_profile_dialogs_multi[talent_id]

    @pyqtSlot(int)
    def on_open_scene_dialog(self, scene_id: int):
        dialog = SceneDialog(self.controller, parent=self.view.window())
        from ui.presenters.scene_planner_presenter import ScenePlannerPresenter
        presenter = ScenePlannerPresenter(self.controller, scene_id, dialog)
        dialog.exec()
        
        current_selection = self.view.talent_list_view.selectionModel().currentIndex()
        if current_selection.isValid():
            talent = current_selection.data(Qt.ItemDataRole.UserRole)
            self.on_talent_selected(talent)