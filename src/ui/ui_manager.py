import logging
from typing import Optional, Type, Callable, Dict

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QDialog, QWidget, QMainWindow

# Data
from data.game_state import Talent

# Windows / Views
from ui.views.start_screen_view import StartScreenView
from ui.windows.talent_profile_window import TalentProfileWindow
from ui.dialogs.email_dialog import EmailDialog
from ui.dialogs.scene_planner_dialog import ScenePlannerDialog
from ui.dialogs.shot_scene_details_dialog import ShotSceneDetailsDialog
from ui.dialogs.go_to_list import GoToTalentDialog
from ui.dialogs.help_dialog import HelpDialog
from ui.dialogs.incomplete_scheduled_scene import IncompleteCastingDialog
from ui.dialogs.interactive_event_dialog import InteractiveEventDialog
from ui.dialogs.save_load_ui import SaveLoadDialog
from ui.dialogs.settings_dialog import SettingsDialog
from ui.dialogs.game_menu_dialog import GameMenuDialog, ExitDialog
from ui.dialogs.shooting_bloc_dialog import ShootingBlocDialog

# Presenters
from ui.presenters.start_screen_presenter import StartScreenPresenter
from ui.presenters.email_presenter import EmailPresenter
from ui.presenters.scene_planner_presenter import ScenePlannerPresenter
from ui.presenters.talent_profile_presenter import TalentProfilePresenter
from ui.presenters.go_to_list_presenter import GoToListPresenter
from ui.presenters.shot_scene_details_presenter import ShotSceneDetailsPresenter
from ui.presenters.game_menu_presenter import GameMenuPresenter

logger = logging.getLogger(__name__)

class UIManager:
    """
    The Assembler and Router of the application.
    Responsibility:
    1. Instantiate Views (Windows/Dialogs).
    2. Instantiate Presenters.
    3. Link View <-> Presenter.
    4. Manage Parent/Child lifecycles to prevent memory leaks or crashes.
    """
    def __init__(self, controller, parent_widget: QWidget = None):
        self.controller = controller
        self.settings_manager = self.controller.settings_manager
        # The main window usually acts as the default parent for dialogs
        self.parent_widget = parent_widget 
        
        # Tracking
        self._dialog_instances: Dict[str, QWidget] = {}
        self._open_scene_dialogs: Dict[int, QWidget] = {}
        self._open_shot_scene_dialogs: Dict[int, QWidget] = {}
        self._talent_profile_window_singleton: Optional[TalentProfileWindow] = None

    # -------------------------------------------------------------------------
    # Core Window Creation (For Application.py)
    # -------------------------------------------------------------------------

    def create_start_screen(self) -> QWidget:
        """
        Creates the Start Screen View and Presenter, links them, and returns the View.
        """
        # 1. Create the View (Dumb)
        view = StartScreenView(parent=self.parent_widget)
        
        # 2. Create the Presenter (Smart), parented to the View
        # The presenter automatically connects signals in its __init__
        presenter = StartScreenPresenter(self.controller, view, self, parent=view)
        
        # 3. Link (Optional, but good for debugging/references if needed later)
        view.presenter = presenter 
        
        return view

    def create_main_window(self) -> QMainWindow:
        """
        Creates the Main Window View and Presenter, injects Tabs, and returns the View.
        """
        # TODO: Implementation pending Refactor Phase 3
        # view = MainWindowView()
        # presenter = MainWindowPresenter(self.controller, view)
        # ... inject tabs ...
        # return view
        pass

    # -------------------------------------------------------------------------
    # Dialog Management Helpers
    # -------------------------------------------------------------------------

    def _get_or_create_singleton_dialog(self, 
                                      dialog_class: Type[QWidget], 
                                      factory_func: Optional[Callable[[], QWidget]] = None) -> QWidget:
        """
        Retrieves an existing singleton dialog or creates a new one.
        
        Args:
            dialog_class: The class to use for the key lookup.
            factory_func: A function that returns the fully assembled (View+Presenter) widget.
                          If None, falls back to legacy instantiation (View(controller)).
        """
        dialog_name = dialog_class.__name__
        if dialog_name not in self._dialog_instances:
            if factory_func:
                dialog = factory_func()
            else:
                # Legacy Fallback: Assumes View takes (controller, parent)
                # TODO: Refactor HelpDialog and GameMenuDialog to remove this path
                dialog = dialog_class(self.controller, parent=self.parent_widget)
            
            # Standard cleanup hook
            dialog.destroyed.connect(lambda: self._on_dialog_closed(dialog_name))
            self._dialog_instances[dialog_name] = dialog
            
        return self._dialog_instances[dialog_name]

    def _on_dialog_closed(self, dialog_name: str):
        if dialog_name in self._dialog_instances:
            del self._dialog_instances[dialog_name]
            logger.info(f"Closed and untracked dialog: {dialog_name}.")

    # -------------------------------------------------------------------------
    # Specific Dialog Show Methods
    # -------------------------------------------------------------------------

    def show_help(self, topic_key: str):
        # TODO: Refactor HelpDialog to MVP.
        dialog = self._get_or_create_singleton_dialog(HelpDialog)
        # We know it's a HelpDialog, so we can call its specific method
        dialog.show_topic(topic_key)

    def show_go_to_list(self):
        def factory():
            dialog = GoToTalentDialog(self.settings_manager, parent=self.parent_widget)
            presenter = GoToListPresenter(self.controller, dialog, self, parent=dialog)
            dialog.set_presenter(presenter)
            return dialog

        dialog = self._get_or_create_singleton_dialog(GoToTalentDialog, factory)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def show_inbox(self):
        def factory():
            dialog = EmailDialog(self.settings_manager, parent=self.parent_widget)
            presenter = EmailPresenter(self.controller, dialog, parent=dialog)
            dialog.set_presenter(presenter)
            return dialog

        dialog = self._get_or_create_singleton_dialog(EmailDialog, factory)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def show_scene_planner(self, scene_id: int):
        """
        Shows a modeless Scene Planner dialog. 
        Tracks instance by scene_id.
        """
        if scene_id in self._open_scene_dialogs:
            dialog = self._open_scene_dialogs[scene_id]
            dialog.raise_()
            dialog.activateWindow()
            QApplication.setActiveWindow(dialog)
            return

        # Creation
        dialog = ScenePlannerDialog(self.settings_manager, parent=self.parent_widget)
        presenter = ScenePlannerPresenter(self.controller, scene_id, dialog, parent=dialog)
        
        if hasattr(dialog, 'set_presenter'):
            dialog.set_presenter(presenter)
        else:
            # Fallback if setter doesn't exist yet (legacy view support)
            dialog.presenter = presenter

        # Cleanup
        dialog.destroyed.connect(lambda: self._on_scene_dialog_closed(scene_id))
        
        self._open_scene_dialogs[scene_id] = dialog
        dialog.show()

    def _on_scene_dialog_closed(self, scene_id: int):
        if scene_id in self._open_scene_dialogs:
            del self._open_scene_dialogs[scene_id]
            logger.info(f"Closed Scene Planner for scene ID: {scene_id}.")

    def show_shot_scene_details(self, scene_id: int, initial_tab: Optional[str] = None):
        if scene_id in self._open_shot_scene_dialogs:
            dialog = self._open_shot_scene_dialogs[scene_id]
            dialog.raise_()
            dialog.activateWindow()
            return

        # Creation
        dialog = ShotSceneDetailsDialog(self.settings_manager, self.parent_widget)
        presenter = ShotSceneDetailsPresenter(
            scene_id, self.controller, dialog, initial_tab=initial_tab, parent=dialog
        )
        dialog.set_presenter(presenter)

        # Cleanup
        # Note: Presenter must disconnect signals on destruction, which happens automatically
        # due to parenting, but explicit disconnect in presenter is safer.
        if hasattr(presenter, 'disconnect_signals'):
            dialog.destroyed.connect(presenter.disconnect_signals)
            
        dialog.destroyed.connect(lambda: self._on_shot_scene_dialog_closed(scene_id))
        
        self._open_shot_scene_dialogs[scene_id] = dialog
        dialog.show()

    def _on_shot_scene_dialog_closed(self, scene_id: int):
        if scene_id in self._open_shot_scene_dialogs:
            del self._open_shot_scene_dialogs[scene_id]
            logger.info(f"Closed Shot Scene Details for scene ID: {scene_id}.")

    def show_talent_profile(self, talent: Talent):
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
        self._talent_profile_window_singleton = None

    # -------------------------------------------------------------------------
    # Simple Modal Dialogs
    # -------------------------------------------------------------------------

    def show_save_load(self, mode: str):
        # TODO: Refactor SaveLoadDialog to use a Presenter if logic grows
        dialog = SaveLoadDialog(self.controller, mode=mode, parent=self.parent_widget)
        if mode == 'load':
            dialog.save_selected.connect(self.controller.load_game)
        elif mode == 'save':
            dialog.save_selected.connect(self.controller.save_game)
        dialog.exec()

    def show_settings_dialog(self):
        dialog = SettingsDialog(self.controller, self.parent_widget)
        dialog.exec()

    def show_game_menu(self):
        def factory():
            # Dumb View
            dialog = GameMenuDialog(parent=self.parent_widget)
            # Logic Wiring
            presenter = GameMenuPresenter(dialog, self, parent=dialog)
            # (Optional) if you want to attach it explicitly, though presenter signals handle it
            dialog.presenter = presenter 
            return dialog

        dialog = self._get_or_create_singleton_dialog(GameMenuDialog, factory)
        dialog.exec()

    def show_exit_dialog(self):
        # 1. Read Setting (Manager logic)
        default_save = self.settings_manager.get_setting("save_on_exit", True)
        
        # 2. Create Dumb View
        dialog = ExitDialog(default_checked=default_save, parent=self.parent_widget)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            exit_save = dialog.get_data()
            
            # 3. Update Setting (Manager logic)
            if exit_save != default_save:
                self.settings_manager.set_setting("save_on_exit", exit_save)
            
            self.controller.return_to_main_menu(exit_save)

    def show_quit_dialog(self):
        default_save = self.settings_manager.get_setting("save_on_exit", True)
        
        dialog = ExitDialog(
            text="Create 'Exit Save' before quitting?",
            default_checked=default_save,
            parent=self.parent_widget,
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            exit_save = dialog.get_data()
            
            if exit_save != default_save:
                self.settings_manager.set_setting("save_on_exit", exit_save)

            self.controller.quit_game(exit_save)

    def show_shooting_bloc_dialog(self, week: int, year: int) -> bool:
        dialog = ShootingBlocDialog(self.controller)
        dialog.set_schedule(week, year)
        return dialog.exec() == QDialog.DialogCode.Accepted

    # -------------------------------------------------------------------------
    # Complex Event Handling (Interactive/Incomplete)
    # -------------------------------------------------------------------------

    def handle_incomplete_scenes(self, scenes: list):
        # Logic contained here involves checking a list and iterating.
        # Ideally this would be in a generic "TurnProcessingPresenter", 
        # but for now, UIManager orchestration is acceptable.
        all_resolved = True
        for scene_data in scenes:
            fresh_scene_data = self.controller.get_scene_by_id(scene_data.id)
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
        scene_data = self.controller.get_scene_by_id(scene_id)
        talent_data = self.controller.get_talent_by_id(talent_id)
        current_money = self.controller.game_state.money

        if not scene_data or not talent_data:
            logger.error(f"[UI ERROR] Missing data for event {event_data.get('id')}")
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
                self.controller.resolve_interactive_event(
                    event_id, scene_id, talent_id, "no_choice_fallback"
                )

    def close_all_dialogs(self):
        """
        Closes and clears all managed dialog instances.
        """
        dialog_list = []
        dialog_list.extend(self._dialog_instances.values())
        if self._talent_profile_window_singleton:
            dialog_list.append(self._talent_profile_window_singleton)
        dialog_list.extend(self._open_scene_dialogs.values())
        dialog_list.extend(self._open_shot_scene_dialogs.values())

        for dialog in dialog_list:
            if dialog:
                # Force deletion to ensure signal disconnection
                dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
                dialog.close()

        self._dialog_instances.clear()
        self._talent_profile_window_singleton = None
        self._open_scene_dialogs.clear()
        self._open_shot_scene_dialogs.clear()

        logger.info("All managed modeless dialogs have been closed.")