import logging
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QDialog, QWidget

from data.game_state import Talent, Scene
from ui.dialogs.email_dialog import EmailDialog
from ui.presenters.email_presenter import EmailPresenter
from ui.dialogs.scene_planner_dialog import ScenePlannerDialog
from ui.presenters.scene_planner_presenter import ScenePlannerPresenter
from ui.windows.talent_profile_window import TalentProfileWindow
from ui.presenters.talent_profile_presenter import TalentProfilePresenter
from ui.dialogs.role_casting_dialog import RoleCastingDialog
from ui.presenters.role_casting_presenter import RoleCastingPresenter
from ui.dialogs.go_to_list import GoToTalentDialog
from ui.presenters.go_to_list_presenter import GoToListPresenter
from ui.dialogs.help_dialog import HelpDialog
from ui.dialogs.incomplete_scheduled_scene import IncompleteCastingDialog
from ui.dialogs.interactive_event_dialog import InteractiveEventDialog
from ui.dialogs.save_load_ui import SaveLoadDialog
from ui.dialogs.settings_dialog import SettingsDialog
from ui.dialogs.shot_scene_details_dialog import ShotSceneDetailsDialog
from ui.presenters.shot_scene_details_presenter import ShotSceneDetailsPresenter
from ui.dialogs.game_menu_dialog import GameMenuDialog, ExitDialog
from ui.dialogs.shooting_bloc_dialog import ShootingBlocDialog

logger = logging.getLogger(__name__)


class UIManager:
    def __init__(self, controller, parent_widget: QWidget = None):
        self.controller = controller
        self.settings_manager = self.controller.settings_manager
        self.parent_widget = parent_widget
        self._dialog_instances = {}
        self._open_scene_dialogs = {}
        self._talent_profile_window_singleton = None
        self._open_shot_scene_dialogs = {}

    def _get_dialog(self, dialog_class, *args, **kwargs):
        dialog_name = dialog_class.__name__
        if dialog_name not in self._dialog_instances:
            self._dialog_instances[dialog_name] = dialog_class(
                self.controller, *args, **kwargs, parent=self.parent_widget
            )
        return self._dialog_instances[dialog_name]
    
    def _on_dialog_closed(self, dialog_name: str):
        if dialog_name in self._dialog_instances:
            del self._dialog_instances[dialog_name]
            logger.info(f"Closed and untracked dialog: {dialog_name}.")

    def show_game_menu(self):
        dialog = self._get_dialog(GameMenuDialog, self)
        dialog.exec()

    def show_go_to_list(self):
        dialog_name = GoToTalentDialog.__name__
        if dialog_name not in self._dialog_instances:
            dialog = GoToTalentDialog(self.settings_manager, parent=self.parent_widget)
            presenter = GoToListPresenter(self.controller, dialog, self, parent=dialog)
            dialog.set_presenter(presenter) # Use a setter for clarity
            
            # Connect the destroyed signal to our cleanup slot.
            dialog.destroyed.connect(lambda obj=None, d_name=dialog_name: self._on_dialog_closed(d_name))

            self._dialog_instances[dialog_name] = dialog
        
        dialog = self._dialog_instances[dialog_name]
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def show_inbox(self):
        dialog_name = EmailDialog.__name__
        if dialog_name not in self._dialog_instances:
            dialog = EmailDialog(self.settings_manager, parent=self.parent_widget)
            presenter = EmailPresenter(self.controller, dialog, parent=dialog)
            dialog.set_presenter(presenter) # Use a setter for clarity
            
            # Connect the destroyed signal to our cleanup slot.
            dialog.destroyed.connect(lambda obj=None, d_name=dialog_name: self._on_dialog_closed(d_name))

            self._dialog_instances[dialog_name] = dialog
        
        dialog = self._dialog_instances[dialog_name]
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def show_help(self, topic_key: str):
        dialog = self._get_dialog(HelpDialog)
        dialog.show_topic(topic_key)

    def show_save_load(self, mode: str):
        dialog = SaveLoadDialog(self.controller, mode=mode, parent=self.parent_widget)
        if mode == 'load':
            dialog.save_selected.connect(self.controller.load_game)
        elif mode == 'save':
            dialog.save_selected.connect(self.controller.save_game)
        result = dialog.exec()

    def show_settings_dialog(self):
        # Since the dialog is modal and self-contained, we create a new instance each time.
        dialog = SettingsDialog(self.controller, self.parent_widget)
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
        This should be called when returning to the main menu to prevent
        orphaned windows.
        """
        dialog_list = []
        dialog_list.extend(self._dialog_instances.values())
        if self._talent_profile_window_singleton:
            dialog_list.append(self._talent_profile_window_singleton)
        dialog_list.extend(self._open_scene_dialogs.values())
        dialog_list.extend(self._open_shot_scene_dialogs.values())

        # We iterate through all known modeless dialogs, force them to delete
        # on close, and then close them.
        for dialog in dialog_list:
            if dialog:
                dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
                dialog.close()

        # Clear all tracking dictionaries to ensure a clean state.
        self._dialog_instances.clear()
        self._talent_profile_window_singleton = None
        self._open_scene_dialogs.clear()
        self._open_shot_scene_dialogs.clear()

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
        talent_data = self.controller.get_talent_by_id(talent_id)
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
    def show_scene_planner(self, scene_id: int):
        """
        Shows a modeless Scene Planner dialog. If one for the given scene_id
        is already open, it brings it to the front.
        """
        if scene_id in self._open_scene_dialogs:
            dialog = self._open_scene_dialogs[scene_id]
            dialog.raise_()
            dialog.activateWindow()
            # On some platforms, activateWindow is not enough
            QApplication.setActiveWindow(dialog)
        else:
            dialog = ScenePlannerDialog(self.settings_manager, parent=self.parent_widget)
            presenter = ScenePlannerPresenter(self.controller, scene_id, dialog, self)
            dialog.presenter = presenter
            
            # Connect the destroyed signal to our cleanup slot.
            # Use a lambda to capture the current scene_id for the connection.
            dialog.destroyed.connect(lambda obj=None, s_id=scene_id: self._on_scene_dialog_closed(s_id))
            
            self._open_scene_dialogs[scene_id] = dialog
            dialog.show()

    def _on_scene_dialog_closed(self, scene_id: int):
        if scene_id in self._open_scene_dialogs:
            del self._open_scene_dialogs[scene_id]
            logger.info(f"Closed and untracked Scene Planner for scene ID: {scene_id}.")

    def show_shot_scene_details(self, scene_id: int, initial_tab: Optional[str] = None):
        """
        Shows a modeless Shot Scene Details dialog. If one for the given
        scene is already open, it brings it to the front.
        This method manages the creation of both the View and the Presenter.
        """
        if scene_id in self._open_shot_scene_dialogs:
            dialog = self._open_shot_scene_dialogs[scene_id]
            dialog.raise_()
            dialog.activateWindow()
        else:
            # UIManager creates both, ensuring a clear ownership hierarchy.
            dialog = ShotSceneDetailsDialog(self.settings_manager, self.parent_widget)
            
            # The presenter is parented to the dialog. When the dialog is destroyed by Qt,
            # the presenter will be destroyed with it, reliably cleaning up signals.
            presenter = ShotSceneDetailsPresenter(scene_id, self.controller, dialog, initial_tab=initial_tab, parent=dialog)
            
            # We use a setter to link them after creation.
            dialog.set_presenter(presenter)

            # Connect the dialog's destruction signal directly to the presenter's cleanup method.
            # This is more reliable than relying solely on closeEvent for signal disconnection.
            dialog.destroyed.connect(presenter.disconnect_signals)
            
            dialog.destroyed.connect(lambda obj=None, s_id=scene_id: self._on_shot_scene_dialog_closed(s_id))
            self._open_shot_scene_dialogs[scene_id] = dialog
            dialog.show()

    def _on_shot_scene_dialog_closed(self, scene_id: int):
        if scene_id in self._open_shot_scene_dialogs:
            del self._open_shot_scene_dialogs[scene_id]
            logger.info(f"Closed and untracked Shot Scene Details for scene ID: {scene_id}.")

    def show_shooting_bloc_dialog(self, week: int, year: int) -> bool:
        """
        Shows a modal dialog to plan a new shooting bloc for a specific week.
        Returns True if the user confirms and the bloc is created, False otherwise.
        """
        # Since this dialog is modal and its presenter is self-contained,
        # we don't need complex tracking like with modeless dialogs.
        dialog = ShootingBlocDialog(self.controller)
        dialog.set_schedule(week, year)
        return dialog.exec() == QDialog.DialogCode.Accepted

    def show_role_casting_dialog(self, scene_id: int, vp_id: int) -> int:
        """
        Shows a modal Role Casting dialog and returns the result code.
        """
        dialog = RoleCastingDialog(self.controller, scene_id, vp_id, parent=self.parent_widget)
        
        # The presenter's lifecycle is tied to the dialog's lifecycle because
        # we parent the presenter to the dialog.
        _ = RoleCastingPresenter(self.controller, dialog, scene_id, vp_id)
        
        return dialog.exec()

    def show_talent_profile(self, talent: Talent):
        """
        Shows a talent profile dialog
        """
        if self._talent_profile_window_singleton is None:
            window = TalentProfileWindow(self.settings_manager, self.parent_widget)
            presenter = TalentProfilePresenter(self.controller, window, self, parent=window)
            window.presenter = presenter
            presenter.open_talent_profile_requested.connect(self.show_talent_profile_by_id)
            window.destroyed.connect(self._on_singleton_profile_closed)
            self._talent_profile_window_singleton = window
            window.show()
        else:
            window = self._talent_profile_window_singleton
        window.presenter.open_talent(talent)
        window.raise_()
        window.activateWindow()
    
    def show_talent_profile_by_id(self, talent_id: int):
        if talent := self.controller.get_talent_by_id(talent_id):
            self.show_talent_profile(talent)

    def _on_singleton_profile_closed(self):
        """
        Slot to clear the reference when the singleton talent profile dialog is closed.
        """
        self._talent_profile_window_singleton = None