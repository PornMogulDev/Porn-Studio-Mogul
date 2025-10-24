import os, logging
from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QMessageBox
from PyQt6.QtGui import QFont
from PyQt6.QtCore import pyqtSlot
import qdarktheme

from data.data_manager import DataManager
from core.game_controller import GameController
from app.start_screen import MenuScreen
from app.main_window import MainGameWindow
from data.settings_manager import SettingsManager 
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin
from utils.paths import LOG_DIR, LOG_FILE

# Set up a logger for this module
logger = logging.getLogger(__name__)

def handle_exception(exc_type, exc_value, exc_traceback):
    """
    Catches unhandled exceptions, logs them using the logging system, 
    and shows a user-friendly dialog.
    """
    # 1. Log the critical error with the full traceback
    # The `exc_info` argument tells the logger to capture the exception information
    logger.critical(
        "Unhandled exception caught by excepthook", 
        exc_info=(exc_type, exc_value, exc_traceback)
    )

    # 2. Display a message to the user
    if not QApplication.instance():
        _ = QApplication([])

    log_file_path = os.path.abspath(os.path.join(LOG_DIR, LOG_FILE))

    error_dialog = QMessageBox()
    error_dialog.setIcon(QMessageBox.Icon.Critical)
    error_dialog.setText("A critical error occurred.")
    error_dialog.setInformativeText(
        f"The application has encountered a serious error and cannot continue.\n\nA detailed report has been saved to:\n\n"
        f"{log_file_path}\n\n"
        "Please provide this file alongside your bug report. Thank you."
    )
    error_dialog.setWindowTitle("Application Error")
    error_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
    error_dialog.exec()

    # The application will now exit after the dialog is closed.

def apply_theme(settings_manager: SettingsManager):
    """Reads theme and font settings and applies them to the application."""
    theme_name = settings_manager.get_setting("theme", "system")
    font_family = settings_manager.font_family
    font_size = settings_manager.font_size

    app = QApplication.instance()
    if not app:
        return

    # Apply font
    font = QFont(font_family, font_size)
    app.setFont(font)

    # Apply theme
    if theme_name == "system":
        app.setStyleSheet("")
    else:
        try:
            app.setStyleSheet(qdarktheme.load_stylesheet(theme_name))
        except TypeError:
            logger.warning(f"Invalid theme '{theme_name}' in settings. Reverting to system default.")
            app.setStyleSheet("")


class ApplicationWindow(QMainWindow, GeometryManagerMixin):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Porn Studio Mogul")
        self.setMinimumSize(1080, 1080)

        self.settings_manager = SettingsManager()
        apply_theme(self.settings_manager)
        self.settings_manager.signals.setting_changed.connect(self._on_setting_changed)

        self.data_manager = DataManager()

        self.controller = GameController(self.settings_manager, self.data_manager)

        self.start_screen = MenuScreen(self.controller)
        self.main_window = MainGameWindow(self.controller)

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self.start_screen)
        self.stacked_widget.addWidget(self.main_window)
        
        self.setCentralWidget(self.stacked_widget)


        self.controller.signals.show_start_screen_requested.connect(self.show_start_screen)
        self.controller.signals.show_main_window_requested.connect(self.show_main_window)
        self.controller.signals.quit_game_requested.connect(self.close)
        self.controller.signals.saves_changed.connect(self.start_screen.refresh_button_states)


        self.show_start_screen()
        self._restore_geometry()

    def show_start_screen(self):
        if self.main_window and self.main_window.ui_manager:
            self.main_window.ui_manager.close_all_dialogs()
        self.start_screen.refresh_button_states()
        self.stacked_widget.setCurrentWidget(self.start_screen)

    def show_main_window(self):
        self.main_window.refresh_all_ui() 
        self.stacked_widget.setCurrentWidget(self.main_window)

    @pyqtSlot(str)
    def _on_setting_changed(self, key: str):
        """
        Listens for changes from the SettingsManager and applies them.
        """
        if key in ("theme", "font_family", "font_size"):
            apply_theme(self.settings_manager)