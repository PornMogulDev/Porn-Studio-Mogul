import logging
from typing import Optional, Type, Callable, Dict

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QDialog, QWidget

#Data
from data.game_state import Talent

# Managers
from ui.managers.icon_manager import IconManager
from ui.managers.tooltip_manager import TooltipManager

# Views
from ui.views.start_screen_view import StartScreenView
from ui.views.main_window_view import MainWindowView
from ui.views.talent_profile_view import TalentProfileWindow

# Tabs
from ui.tabs.talent_tab import TalentTab
from ui.tabs.scenes_tab import ScenesTab
from ui.tabs.schedule_tab import ScheduleTab
from ui.tabs.market_tab import MarketTab
from ui.tabs.ai_studios_tab import AIStudiosTab

# Tab Presenters
from ui.presenters.talent_tab_presenter import TalentTabPresenter
from ui.presenters.scenes_tab_presenter import ScenesTabPresenter
from ui.presenters.schedule_tab_presenter import ScheduleTabPresenter
from ui.presenters.market_tab_presenter import MarketTabPresenter
from ui.presenters.ai_studios_tab_presenter import AIStudiosTabPresenter

# Dialogs
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
from ui.dialogs.call_sheet_dialog import CallSheetDialog
from ui.dialogs.policy_dialog import PolicyDialog
from ui.dialogs.roster_window import RosterWindow

# Presenters
from ui.presenters.start_screen_presenter import StartScreenPresenter
from ui.presenters.main_window_presenter import MainWindowPresenter
from ui.presenters.email_presenter import EmailPresenter
from ui.presenters.scene_planner_presenter import ScenePlannerPresenter
from ui.presenters.talent_profile_presenter import TalentProfilePresenter
from ui.presenters.go_to_list_presenter import GoToListPresenter
from ui.presenters.shot_scene_details_presenter import ShotSceneDetailsPresenter
from ui.presenters.game_menu_presenter import GameMenuPresenter
from ui.presenters.call_sheet_presenter import CallSheetPresenter
from ui.presenters.policy_presenter import PolicyPresenter
from ui.presenters.roster_presenter import RosterPresenter

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
    def __init__(self, controller,  icon_manager: IconManager, parent_widget: QWidget = None):
        self.controller = controller
        self.icon_manager = icon_manager
        self.settings_manager = self.controller.settings_manager
        # The main window usually acts as the default parent for dialogs
        self.parent_widget = parent_widget

        # Tracking
        self._dialog_instances: Dict[str, QWidget] = {}
        self._open_scene_dialogs: Dict[int, QWidget] = {}
        self._open_shot_scene_dialogs: Dict[int, QWidget] = {}
        self._talent_profile_window_singleton: Optional[TalentProfileWindow] = None
        
        # Dedicated manager for tooltips
        self.tooltip_manager = TooltipManager(self.controller, self.icon_manager, self.parent_widget)

        # Keep references to main presenters to prevent GC if not parented correctly
        self.main_presenter = None
        self.tab_presenters = []

        # Listen for Alt-Tab events to hide tooltips
        QApplication.instance().applicationStateChanged.connect(self._on_app_state_changed)

# -------------------------------------------------------------------------
# Core Window Creation (For Application.py)
# -------------------------------------------------------------------------

    def create_start_screen(self) -> QWidget:
        view = StartScreenView(parent=self.parent_widget)
        presenter = StartScreenPresenter(self.controller, view, self, parent=view)
        view.presenter = presenter 
        return view

    def create_main_window(self) -> MainWindowView:
        """
        Creates the Main Window View and Presenter, injects Tabs, and returns the View.
        """
        # 1. Create the View (Dumb Shell)
        # Inject theme_manager so the view can handle visual components (like Notifications)
        # The controller holds the theme_manager instance created in ApplicationWindow
        view = MainWindowView(
            self.settings_manager, 
            self.controller.theme_manager, 
            self.icon_manager,
            parent=None
        ) 
        
        # 2. Create the Presenter (Smart Logic)
        # Parent the presenter to the view so it dies when the window closes
        self.main_presenter = MainWindowPresenter(self.controller, view, self, parent=view)
        
        # 3. Inject Tabs (View + Presenter construction)
        self._assemble_tabs(view)

        # Note: We do NOT load data here anymore. That happens when the window is shown.
        return view

    def _assemble_tabs(self, main_view: MainWindowView):
        """Helper to build tabs and inject them into the main window."""
        
        # -- Schedule Tab --
        schedule_view = ScheduleTab(self.icon_manager)
        schedule_presenter = ScheduleTabPresenter(
            self.controller, schedule_view, self, parent=schedule_view
        )
        self.tab_presenters.append(schedule_presenter)
        main_view.add_tab(schedule_view, "Schedule")

        # -- Talent Tab --
        talent_view = TalentTab(self.icon_manager)
        talent_presenter = TalentTabPresenter(
            self.controller, talent_view, self, self.icon_manager, parent=talent_view
        )
        self.tab_presenters.append(talent_presenter)
        main_view.add_tab(talent_view, "Talent")

        # -- Scenes Tab --
        scenes_view = ScenesTab()
        scenes_presenter = ScenesTabPresenter(
            self.controller, scenes_view, self, parent=scenes_view
        )
        self.tab_presenters.append(scenes_presenter)
        main_view.add_tab(scenes_view, "Scenes")

        # -- Market Tab --
        market_view = MarketTab(self.icon_manager)
        market_presenter = MarketTabPresenter(
            self.controller, market_view, parent=market_view
        )
        self.tab_presenters.append(market_presenter)
        main_view.add_tab(market_view, "Market")

        # -- AI Studios Tab --
        ai_studios_view = AIStudiosTab(self.controller.theme_manager, self.settings_manager)
        ai_studios_presenter = AIStudiosTabPresenter(
            self.controller, ai_studios_view, parent=ai_studios_view
        )
        self.tab_presenters.append(ai_studios_presenter)
        main_view.add_tab(ai_studios_view, "AI Studios")

    def refresh_main_window_data(self):
        """
        Called by Application.py when the main window is shown (after game load).
        Triggers all presenters to fetch fresh data.
        """
        if self.main_presenter:
            self.main_presenter.load_initial_data()
        
        for presenter in self.tab_presenters:
            if hasattr(presenter, 'load_initial_data'):
                presenter.load_initial_data()
            elif hasattr(presenter, 'view') and hasattr(presenter.view, 'refresh_from_state'):
                # Handle TalentTab which uses a different pattern
                presenter.view.refresh_from_state()

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
                # TODO: Refactor HelpDialog and to remove this path
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
    # Smart Hover / Summary Card
    # -------------------------------------------------------------------------

    def show_talent_summary(self, talent_id: int, global_pos):
        """
        Delegates to TooltipManager.
        """
        self.tooltip_manager.show_talent_summary(talent_id, global_pos)

    def hide_talent_summary(self):
        """Hides the summary card."""
        self.tooltip_manager.hide_summary()

    def _on_app_state_changed(self, state):
        """Forces tooltips to hide if the application loses focus (Alt-Tab)."""
        if state != Qt.ApplicationState.ApplicationActive:
            self.hide_talent_summary()

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
        logger.info("[UIManager] show_inbox() called")
    
        def factory():
            logger.info("[UIManager] Creating new EmailDialog and EmailPresenter")
            dialog = EmailDialog(self.settings_manager, self.icon_manager, parent=self.parent_widget)
            presenter = EmailPresenter(self.controller, dialog, parent=dialog)
            dialog.set_presenter(presenter)
            
            # --- Wiring Smart Links ---
            dialog.smart_link_hover_entered.connect(self.show_talent_summary)
            dialog.smart_link_hover_left.connect(self.hide_talent_summary)
            dialog.smart_link_alt_clicked.connect(self.show_talent_profile_by_id)

            logger.info(f"[UIManager] EmailDialog created: {id(dialog)}, EmailPresenter created: {id(presenter)}")
            return dialog

        dialog = self._get_or_create_singleton_dialog(EmailDialog, factory)
        logger.info(f"[UIManager] Using EmailDialog: {id(dialog)}")
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def show_policy_dialog(self):
        def factory():
            dialog = PolicyDialog(self.settings_manager, parent=self.parent_widget)
            presenter = PolicyPresenter(self.controller, dialog, parent=dialog)
            dialog.set_presenter(presenter)
            presenter.initialize()
            return dialog

        dialog = self._get_or_create_singleton_dialog(PolicyDialog, factory)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def show_roster(self):
        def factory():
            dialog = RosterWindow(self.settings_manager, self.icon_manager, parent=self.parent_widget)
            presenter = RosterPresenter(self.controller, dialog, self, parent=dialog)
            dialog.set_presenter(presenter)
            return dialog

        dialog = self._get_or_create_singleton_dialog(RosterWindow, factory)
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
        # Pass self (UIManager) so the summary widget inside can request tooltips/profiles
        dialog = ScenePlannerDialog(self.settings_manager, self.icon_manager, ui_manager=self, parent=self.parent_widget)
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
        dialog = ShotSceneDetailsDialog(self.settings_manager, parent=self.parent_widget, ui_manager=self)
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
        # Ensure any floating summary card is hidden when opening the full profile
        self.hide_talent_summary()

        if self._talent_profile_window_singleton is None:
            window = TalentProfileWindow(self.settings_manager, self.icon_manager, self.parent_widget)
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
            dialog = GameMenuDialog(self.settings_manager, parent=self.parent_widget)
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

    def show_call_sheet_dialog(self, week: int, year: int) -> bool:
        # 1. Create View (Dumb)
        dialog = CallSheetDialog(self.settings_manager, self.icon_manager, parent=self.parent_widget)
        
        # 2. Create Presenter (Smart, Parented to View)
        presenter = CallSheetPresenter(self.controller, dialog, parent=dialog)
        
        # 3. Link, Initialize, and Configure
        dialog.set_presenter(presenter)
        presenter.initialize()
        dialog.set_schedule_values(week, year)
        
        # 4. Execute
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
        current_money = self.controller.game_state.studio.money

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
        logger.info("[UIManager] close_all_dialogs() called, cleaning up presenters...")
        
        dialog_list = []
        dialog_list.extend(self._dialog_instances.values())
        if self._talent_profile_window_singleton:
            dialog_list.append(self._talent_profile_window_singleton)
        dialog_list.extend(self._open_scene_dialogs.values())
        dialog_list.extend(self._open_shot_scene_dialogs.values())
        
        self.tooltip_manager.cleanup()

        for dialog in dialog_list:
            if dialog:
                # Explicitly call cleanup on the presenter before closing the dialog
                if hasattr(dialog, 'presenter') and dialog.presenter and hasattr(dialog.presenter, 'cleanup'):
                    try:
                        dialog.presenter.cleanup()
                    except Exception as e:
                        logger.warning(f"Error during presenter cleanup for {type(dialog).__name__}: {e}")

                # Force deletion to ensure signal disconnection for other Qt reasons
                dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
                dialog.close()

        self._dialog_instances.clear()
        self._talent_profile_window_singleton = None
        self._open_scene_dialogs.clear()
        self._open_shot_scene_dialogs.clear()

        logger.info("All managed modeless dialogs have been closed.")