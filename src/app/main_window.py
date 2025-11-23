import logging
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QMessageBox, QWidget, QVBoxLayout,
)

from core.notifications_manager import NotificationManager
from ui.tabs.talent_tab import TalentTab
from ui.tabs.scenes_tab import ScenesTab
from ui.tabs.schedule_tab import ScheduleTab
from ui.tabs.market_tab import MarketTab
from ui.presenters.talent_tab_presenter import TalentTabPresenter
from ui.presenters.scenes_tab_presenter import ScenesTabPresenter
from ui.presenters.schedule_tab_presenter import ScheduleTabPresenter
from ui.presenters.market_tab_presenter import MarketTabPresenter
from ui.widgets.main_window.detachable_tab_widget import DetachableTabWidget
from ui.widgets.main_window.top_bar_widget import TopBarWidget
from ui.widgets.main_window.bottom_bar_widget import BottomBarWidget
from utils import time_utils

logger = logging.getLogger(__name__)

class MainGameWindow(QWidget):
    def __init__(self, controller, ui_manager):
        super().__init__()
        self.controller = controller
        self.ui_manager = ui_manager
        self.talent_tab_presenter = None
        self.setup_ui()
        self.notification_manager = NotificationManager(self, controller)
        self._create_actions()

        # --- Global Signal Connections ---
        self.controller.signals.notification_posted.connect(self.notification_manager.show_notification)
        self.controller.signals.game_over_triggered.connect(self.game_over_ui)
        self.controller.signals.incomplete_scene_check_requested.connect(self.ui_manager.handle_incomplete_scenes)
        self.controller.signals.interactive_event_triggered.connect(self.ui_manager.show_interactive_event)
        self.controller.signals.show_help_requested.connect(self.ui_manager.show_help)
        
        # --- Data binding signals for Bars ---
        # Note: In Phase 3, these will move to MainWindowPresenter
        self.controller.signals.money_changed.connect(self._on_money_changed)
        self.controller.signals.time_changed.connect(self._on_time_changed)
        self.controller.signals.emails_changed.connect(self._on_emails_changed)
        self.controller.settings_manager.signals.setting_changed.connect(self._on_setting_changed)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # --- Top bar (Dumb View) ---
        self.top_bar = TopBarWidget(parent=self)
        
        # Connect TopBar signals
        self.top_bar.menu_clicked.connect(self.ui_manager.show_game_menu)
        self.top_bar.next_week_clicked.connect(self.controller.advance_week)
        self.top_bar.help_requested.connect(self.ui_manager.show_help)
        
        layout.addWidget(self.top_bar)

        # --- Tabs ---
        tabs = DetachableTabWidget(self.controller.settings_manager)
        
        self.talent_tab = TalentTab()
        self.talent_tab_presenter = TalentTabPresenter(self.controller, self.talent_tab, self.ui_manager)

        self.scenes_tab = ScenesTab()
        self.scenes_tab_presenter = ScenesTabPresenter(self.controller, self.scenes_tab, self.ui_manager, parent=self.scenes_tab)
        
        self.schedule_tab = ScheduleTab()
        self.schedule_tab_presenter = ScheduleTabPresenter(self.controller, self.schedule_tab, self.ui_manager, parent=self.schedule_tab)

        self.market_tab = MarketTab()
        self.market_tab_presenter = MarketTabPresenter(self.controller, self.market_tab, parent=self.market_tab)

        tabs.addTab(self.schedule_tab, "Schedule")
        tabs.addTab(self.talent_tab, "Talent")
        tabs.addTab(self.scenes_tab, "Scenes")
        tabs.addTab(self.market_tab, "Market")
        
        layout.addWidget(tabs)

        # Bottom layout (Dumb View)
        self.bottom_bar = BottomBarWidget(parent=self)
        
        # Connect BottomBar signals
        self.bottom_bar.inbox_clicked.connect(self.ui_manager.show_inbox)
        self.bottom_bar.go_to_list_clicked.connect(self.ui_manager.show_go_to_list)
        
        layout.addWidget(self.bottom_bar)

    def _create_actions(self):
        # Game Menu Action
        menu_action = QAction(self)
        menu_action.setShortcut(QKeySequence(Qt.Key.Key_Escape))
        menu_action.triggered.connect(self.ui_manager.show_game_menu)
        self.addAction(menu_action)

        # Advance Week Action
        advance_week_action = QAction(self)
        advance_week_action.setShortcut(QKeySequence(Qt.Key.Key_P))
        advance_week_action.triggered.connect(self.controller.advance_week)
        self.addAction(advance_week_action)

        # Quick Save Action
        quick_save_action = QAction(self)
        quick_save_action.setShortcut(QKeySequence(Qt.Key.Key_F5))
        quick_save_action.triggered.connect(self.controller.quick_save)
        self.addAction(quick_save_action)

        # Quick Load Action
        quick_load_action = QAction(self)
        quick_load_action.setShortcut(QKeySequence(Qt.Key.Key_F9))
        quick_load_action.triggered.connect(self.controller.quick_load)
        self.addAction(quick_load_action)

    def load_ui(self):
        """Pulls all current data from the controller and updates the entire UI."""
        # Manually trigger updates for bars
        self._on_money_changed(self.controller.game_state.money)
        
        year, week = time_utils.from_absolute(self.controller.game_state.absolute_week)
        self._on_time_changed(week, year)
        
        self._on_emails_changed() # Trigger inbox update

        if self.talent_tab_presenter:
            self.talent_tab_presenter.view.refresh_from_state()

        if self.scenes_tab_presenter:
            self.scenes_tab_presenter.load_initial_data()
        
        if self.schedule_tab_presenter:
            self.schedule_tab_presenter.load_initial_data()
        
        if self.market_tab_presenter:
            self.market_tab_presenter.load_initial_data()

    # --- Data Update Handlers (Temporary Presenter Logic) ---

    def _on_money_changed(self, money: int):
        self.top_bar.update_money_display(money)

    def _on_time_changed(self, week: int, year: int):
        self.top_bar.update_time_display(week, year)

    def _on_emails_changed(self):
        """Fetches unread count and pushes primitive int to BottomBar."""
        unread_count = self.controller.get_unread_email_count()
        self.bottom_bar.update_inbox_count(unread_count)

    @pyqtSlot(str)
    def _on_setting_changed(self, key: str):
        if key in ("font_family", "font_size"):
            # Update the bottom bar's font
            font = self.controller.settings_manager.get_app_font()
            self.bottom_bar.setFont(font)
            # Re-apply emails update in case theme/font affected style
            self._on_emails_changed()

    def game_over_ui(self, reason: str):
        self.setEnabled(False) 

        if reason == "bankruptcy":
            msg = QMessageBox()
            msg.setWindowTitle("Game Over: Bankruptcy")
            msg.setInformativeText("You accumulated too much debt. Game is over.")
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.exec() 
            self.controller.handle_game_over()

        self.setEnabled(True)