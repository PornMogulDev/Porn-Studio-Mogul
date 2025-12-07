import logging
from PyQt6.QtCore import QObject, pyqtSlot

from utils import time_utils

logger = logging.getLogger(__name__)

class MainWindowPresenter(QObject):
    def __init__(self, controller, view, ui_manager, parent=None):
        """
        Args:
            controller: GameController
            view: MainWindowView
            ui_manager: UIManager
        """
        super().__init__(parent)
        self.controller = controller
        self.view = view
        self.ui_manager = ui_manager

        self._connect_signals()
        
    def _connect_signals(self):
        # --- Controller State Signals ---
        self.controller.signals.money_changed.connect(self._on_money_changed)
        self.controller.signals.time_changed.connect(self._on_time_changed)
        self.controller.signals.emails_changed.connect(self._on_emails_changed)
        self.controller.signals.notification_posted.connect(self.view.show_notification)
        self.controller.signals.game_over_triggered.connect(self._on_game_over)

        # --- UI Request Signals ---
        self.controller.signals.incomplete_scene_check_requested.connect(self.ui_manager.handle_incomplete_scenes)
        self.controller.signals.interactive_event_triggered.connect(self.ui_manager.show_interactive_event)
        self.controller.signals.show_help_requested.connect(self.ui_manager.show_help)

        # --- Settings Signals ---
        self.controller.settings_manager.signals.setting_changed.connect(self._on_setting_changed)

        # --- View Component Signals ---
        # Top Bar
        self.view.top_bar.menu_clicked.connect(self.ui_manager.show_game_menu)
        self.view.top_bar.inbox_clicked.connect(self.ui_manager.show_inbox)
        self.view.top_bar.next_week_clicked.connect(self.controller.advance_week)
        self.view.top_bar.help_requested.connect(self.ui_manager.show_help)
        
        # Bottom Bar
        self.view.bottom_bar.go_to_list_clicked.connect(self.ui_manager.show_go_to_list)
        self.view.bottom_bar.policies_clicked.connect(self.ui_manager.show_policy_dialog)

        # --- Actions (Hotkeys) ---
        self.view.action_menu.triggered.connect(self.ui_manager.show_game_menu)
        self.view.action_advance_week.triggered.connect(self.controller.advance_week)
        self.view.action_quick_save.triggered.connect(self.controller.quick_save)
        self.view.action_quick_load.triggered.connect(self.controller.quick_load)

    def load_initial_data(self):
        """Populates the view with current state on startup."""
        self._on_money_changed(self.controller.game_state.studio.money)
        
        # GameController emits/stores (year, week_of_year)
        # We transform to (year, month, week_in_month) for display
        abs_week = self.controller.game_state.absolute_week
        year, month, week = time_utils.to_month(abs_week)
        self.view.update_time(month, week, year)
        
        self._on_emails_changed()

    # --- Event Handlers ---

    @pyqtSlot(int)
    def _on_money_changed(self, money: int):
        self.view.update_money(money)

    @pyqtSlot(int, int)
    def _on_time_changed(self, week: int, year: int):
        # Controller emits week as 1-52 (week of year)
        # We must calculate the specific month and week-in-month
        abs_week = time_utils.to_absolute(year, week)
        _, month, week_in_month = time_utils.to_month(abs_week)
        self.view.update_time(month, week_in_month, year)

    @pyqtSlot()
    def _on_emails_changed(self):
        count = self.controller.get_unread_email_count()
        self.view.update_inbox_count(count)

    @pyqtSlot(str)
    def _on_game_over(self, reason: str):
        if reason == "bankruptcy":
            self.view.show_game_over_dialog(
                "Game Over: Bankruptcy",
                "You accumulated too much debt. The studio has been closed."
            )
            self.controller.handle_game_over()
        # Add other reasons here as needed

    @pyqtSlot(str)
    def _on_setting_changed(self, key: str):
        if key in ("font_family", "font_size"):
            font = self.controller.settings_manager.get_app_font()
            self.view.set_font_from_settings(font)