from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QMessageBox
)

from ui.widgets.main_window.detachable_tab_widget import DetachableTabWidget
from ui.widgets.main_window.top_bar_widget import TopBarWidget
from ui.widgets.main_window.bottom_bar_widget import BottomBarWidget
from core.notifications_manager import NotificationManager

class MainWindowView(QWidget):
    """
    The main game interface shell. 
    It holds the Top Bar, the Tab Widget, and the Bottom Bar.
    It knows NOTHING about the GameController.
    """
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        # We need settings_manager for the DetachableTabWidget's internal logic 
        # (restoring detached windows), but that's a UI-specific dependency.
        self.settings_manager = settings_manager
        
        self.setup_ui()
        self._create_actions()
        
        # Initialize Notification Manager (View-side display logic)
        # Passing None for controller as we will drive it manually via Presenter
        self.notification_manager = NotificationManager(self, None)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # --- Top Bar ---
        self.top_bar = TopBarWidget(parent=self)
        layout.addWidget(self.top_bar)

        # --- Tabs ---
        self.tabs = DetachableTabWidget(self.settings_manager, parent=self)
        layout.addWidget(self.tabs)

        # --- Bottom Bar ---
        self.bottom_bar = BottomBarWidget(parent=self)
        layout.addWidget(self.bottom_bar)

    def _create_actions(self):
        """Creates standard actions. The Presenter will connect them."""
        self.action_menu = QAction("Menu", self)
        self.action_menu.setShortcut(QKeySequence(Qt.Key.Key_Escape))
        self.addAction(self.action_menu)

        self.action_advance_week = QAction("Advance Week", self)
        self.action_advance_week.setShortcut(QKeySequence(Qt.Key.Key_P))
        self.addAction(self.action_advance_week)

        self.action_quick_save = QAction("Quick Save", self)
        self.action_quick_save.setShortcut(QKeySequence(Qt.Key.Key_F5))
        self.addAction(self.action_quick_save)

        self.action_quick_load = QAction("Quick Load", self)
        self.action_quick_load.setShortcut(QKeySequence(Qt.Key.Key_F9))
        self.addAction(self.action_quick_load)

    # --- Public API for Presenter/Assembler ---

    def add_tab(self, widget: QWidget, title: str):
        self.tabs.addTab(widget, title)

    def show_notification(self, message: str, notification_type: str = "info"):
        self.notification_manager.show_notification(message, notification_type)

    def show_game_over_dialog(self, title: str, message: str):
        # We disable input on the main window during the dialog
        self.setEnabled(False) 
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setInformativeText(message)
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.exec() 
        self.setEnabled(True)

    def update_money(self, money: int):
        self.top_bar.update_money_display(money)

    def update_time(self, week: int, year: int):
        self.top_bar.update_time_display(week, year)

    def update_inbox_count(self, count: int):
        self.bottom_bar.update_inbox_count(count)
    
    def set_font_from_settings(self, font):
        """Called when font settings change."""
        self.bottom_bar.setFont(font)