import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog

from data.game_state import Talent
from ui.dialogs.email_dialog import EmailDialog
from ui.dialogs.talent_profile_dialog import TalentProfileDialog
from ui.dialogs.go_to_list import GoToTalentDialog
from ui.dialogs.help_dialog import HelpDialog
from ui.dialogs.incomplete_scheduled_scene import IncompleteCastingDialog
from ui.dialogs.interactive_event_dialog import InteractiveEventDialog
from ui.dialogs.save_load_ui import SaveLoadDialog
from ui.dialogs.settings_dialog import SettingsDialog
from ui.dialogs.game_menu_dialog import GameMenuDialog, ExitDialog

logger = logging.getLogger(__name__)


class UIManager:
    def __init__(self, controller, parent_widget=None):
        self.controller = controller
        self.parent_widget = parent_widget
        self._dialog_instances = {}
        self._talent_profile_dialog_singleton = None
        self._open_profile_dialogs_multi = {}

    def _get_dialog(self, dialog_class, *args, **kwargs):
        dialog_name = dialog_class.__name__
        if dialog_name not in self._dialog_instances:
            self._dialog_instances[dialog_name] = dialog_class(
                self.controller, *args, **kwargs, parent=self.parent_widget
            )
        return self._dialog_instances[dialog_name]

    def show_game_menu(self):
        dialog = self._get_dialog(GameMenuDialog)
        dialog.exec()

    def show_go_to_list(self):
        dialog_name = GoToTalentDialog.__name__
        if dialog_name not in self._dialog_instances:
            # Pass self (the UIManager instance) to the dialog for profile handling
            self._dialog_instances[dialog_name] = GoToTalentDialog(
                self.controller, self, parent=self.parent_widget
            )
        
        dialog = self._dialog_instances[dialog_name]
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def show_inbox(self):
        dialog = self._get_dialog(EmailDialog)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def show_help(self, topic_key: str):
        dialog = self._get_dialog(HelpDialog)
        dialog.show_topic(topic_key)

    def show_save_load(self, mode: str):
        dialog = SaveLoadDialog(self.controller, mode=mode, parent=self.parent_widget)
        dialog.exec()

    def show_settings(self):
        dialog = self._get_dialog(SettingsDialog)
        dialog.exec()

    def show_exit_dialog(self):
        dialog = ExitDialog(self.controller, parent=self.parent_widget)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            exit_save = dialog.get_data()
            self.controller.return_to_main_menu(exit_save)

    def show_quit_dialog(self):
        dialog = ExitDialog(
            self.controller,
            text="Create 'Exit Save' before quitting?",
            parent=self.parent_widget,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            exit_save = dialog.get_data()
            self.controller.quit_game(exit_save)

    def close_all_dialogs(self):
        """
        Closes and clears all managed dialog instances.
+        This should be called when returning to the main menu to prevent
       orphaned windows.
        """
        dialog_list = []
        dialog_list.extend(self._dialog_instances.values())
        if self._talent_profile_dialog_singleton:
            dialog_list.append(self._talent_profile_dialog_singleton)
        dialog_list.extend(self._open_profile_dialogs_multi.values())

        # We iterate through all known modeless dialogs, force them to delete
        # on close, and then close them.
        for dialog in dialog_list:
            if dialog:
                dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
                dialog.close()

        # Clear all tracking dictionaries to ensure a clean state.
        self._dialog_instances.clear()
        self._talent_profile_dialog_singleton = None
        self._open_profile_dialogs_multi.clear()

        logger.info("All managed modeless dialogs have been closed and references cleared.")

    def handle_incomplete_scenes(self, scenes: list):
        all_resolved = True
        for scene_data in scenes:
            fresh_scene_data = self.controller.get_scene_for_planner(scene_data.id)
            if not fresh_scene_data:
                continue

            dialog = IncompleteCastingDialog(
                fresh_scene_data, self.controller, self.parent_widget
            )
            result = dialog.exec()

            if result == QDialog.DialogCode.Rejected:
                all_resolved = False
                self.controller.signals.notification_posted.emit(
                    "Week advancement cancelled."
                )
                break

        if all_resolved:
            self.controller.advance_week()

    def show_interactive_event(self, event_data: dict, scene_id: int, talent_id: int):
        scene_data = self.controller.get_scene_for_planner(scene_id)
        talent_data = self.controller.talent_service.get_talent_by_id(talent_id)
        current_money = self.controller.game_state.money

        if not scene_data or not talent_data:
            logger.error(
                f"[UI ERROR] Could not fetch required data for event ID '{event_data.get('id')}'. Scene: {scene_data}, Talent: {talent_data}"
            )
            self.controller.resolve_interactive_event(
                event_data["id"], scene_id, talent_id, "error_fallback"
            )
            return

        dialog = InteractiveEventDialog(
            event_data=event_data,
            scene_data=scene_data,
            talent_data=talent_data,
            current_money=current_money,
            controller=self.controller,
            parent=self.parent_widget,
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            choice_id = dialog.selected_choice_id
            event_id = event_data["id"]

            if choice_id:
                self.controller.resolve_interactive_event(
                    event_id, scene_id, talent_id, choice_id
                )
            else:
                logger.error(
                    f"[UI WARN] Event dialog for '{event_id}' was accepted but no choice ID was returned. Resuming."
                )
                self.controller.resolve_interactive_event(
                    event_id, scene_id, talent_id, "no_choice_fallback"
                )
                
    def show_talent_profile(self, talent: Talent):
        """
        Shows a talent profile dialog, respecting the user's setting for
        singleton or multiple dialog behavior.
        """
        behavior = self.controller.settings_manager.get_setting("talent_profile_dialog_behavior")
        
        if behavior == 'singleton':
            if self._talent_profile_dialog_singleton is None:
                dialog = TalentProfileDialog(talent, self.controller, self.parent_widget)
                dialog.destroyed.connect(self._on_singleton_profile_closed)
                self._talent_profile_dialog_singleton = dialog
                dialog.show()
            else:
                self._talent_profile_dialog_singleton.update_with_talent(talent)
                self._talent_profile_dialog_singleton.raise_()
                self._talent_profile_dialog_singleton.activateWindow()
        else: # 'multiple'
            talent_id = talent.id
            if talent_id in self._open_profile_dialogs_multi:
                dialog = self._open_profile_dialogs_multi[talent_id]
                dialog.raise_()
                dialog.activateWindow()
            else:
                dialog = TalentProfileDialog(talent, self.controller, self.parent_widget)
                dialog.destroyed.connect(
                    lambda obj=None, t_id=talent_id: self._on_multi_profile_closed(t_id)
                )
                self._open_profile_dialogs_multi[talent_id] = dialog
                dialog.show()

    def _on_singleton_profile_closed(self):
        """
        Slot to clear the reference when the singleton talent profile dialog is closed.
        """
        self._talent_profile_dialog_singleton = None

    def _on_multi_profile_closed(self, talent_id: int):
        """
        Slot to remove a specific multi-instance talent profile dialog from the
        tracking dictionary when it's closed.
        """
        if talent_id in self._open_profile_dialogs_multi:
            del self._open_profile_dialogs_multi[talent_id]