import logging
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QMessageBox, QTabWidget, QWidget, QVBoxLayout,
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

        # --- Signal Connections ---
        self.controller.signals.notification_posted.connect(self.notification_manager.show_notification)
        self.controller.signals.game_over_triggered.connect(self.game_over_ui)
        self.controller.signals.incomplete_scene_check_requested.connect(self.ui_manager.handle_incomplete_scenes)
        self.controller.signals.interactive_event_triggered.connect(self.ui_manager.show_interactive_event)
        self.controller.signals.show_help_requested.connect(self.ui_manager.show_help)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # --- Top bar ---
        self.top_bar = TopBarWidget(self.controller)
        self.top_bar.set_menu_callback(self.ui_manager.show_game_menu)
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

        # Bottom layout
        self.bottom_bar = BottomBarWidget(self.controller)
        self.bottom_bar.set_inbox_callback(self.ui_manager.show_inbox)
        self.bottom_bar.set_go_to_list_callback(self.ui_manager.show_go_to_list)
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
        self.top_bar.update_initial_state()
        self.bottom_bar.update_initial_state()

        if self.talent_tab_presenter:
            self.talent_tab_presenter.view.refresh_from_state()

        if self.scenes_tab_presenter:
            self.scenes_tab_presenter.load_initial_data()
        
        if self.schedule_tab_presenter:
            self.schedule_tab_presenter.load_initial_data()
        
        if self.market_tab_presenter:
            self.market_tab_presenter.load_initial_data()

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