import os, logging
from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QMessageBox
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtCore import pyqtSlot, QSize

from data.data_manager import DataManager
from data.save_manager import SaveManager
from data.settings_manager import SettingsManager
from core.service_container import ServiceContainer
from core.game_signals import GameSignals
from core.game_controller import GameController
from app.start_screen import MenuScreen
from app.main_window import MainGameWindow
from ui.ui_manager import UIManager
from ui.theme_manager import ThemeManager 
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

def apply_theme(settings_manager: SettingsManager, theme_manager: ThemeManager):
    """
    Applies the theme and font settings using the ThemeManager.
    """
    app = QApplication.instance()
    if not app:
        return

    # 1. Get settings
    theme_name = settings_manager.get_setting("theme", "light") # Default to light
    font_family = settings_manager.font_family
    font_size = settings_manager.font_size

    if theme_name == "system":
        app.setStyleSheet("") # Clear any existing stylesheet to revert to default
        return

    # 2. Get the theme data object
    current_theme = theme_manager.get_theme(theme_name)
    
    # 3. Generate the final stylesheet
    final_stylesheet = theme_manager.generate_stylesheet(
        theme=current_theme,
        font_family=font_family,
        font_size=font_size
    )

    # 4. Apply it
    app.setStyleSheet(final_stylesheet)


class ApplicationWindow(QMainWindow, GeometryManagerMixin):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Porn Studio Mogul")
        self.defaultSize = QSize(1920, 1080)

        self.settings_manager = SettingsManager()
        self.theme_manager = ThemeManager(self.settings_manager)
        apply_theme(self.settings_manager, self.theme_manager)
        self.settings_manager.signals.setting_changed.connect(self._on_setting_changed)

        # --- Create long-lived application components ---
        self.data_manager = DataManager()
        self.signals = GameSignals()
        self.save_manager = SaveManager()

        # --- Create the Composition Root for services ---
        self.service_container = ServiceContainer(self.data_manager, self.save_manager, self.signals)

        # --- Create the Controller (Façade) ---
        self.controller = GameController(self.settings_manager, self.data_manager, self.theme_manager,
                                         self.save_manager, self.signals, self.service_container)
        self.ui_manager = UIManager(self.controller, self)
        
        self.start_screen = MenuScreen(self.controller, self.ui_manager)
        self.main_window = MainGameWindow(self.controller, self.ui_manager)

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
        self.ui_manager.close_all_dialogs()
        self.start_screen.refresh_button_states()
        self.stacked_widget.setCurrentWidget(self.start_screen)

    def show_main_window(self):
        self.main_window.load_ui() 
        self.stacked_widget.setCurrentWidget(self.main_window)

    @pyqtSlot(str)
    def _on_setting_changed(self, key: str):
        """
        Listens for changes from the SettingsManager and applies them.
        """
        if key in ("theme", "font_family", "font_size"):
            apply_theme(self.settings_manager, self.theme_manager)

    def closeEvent(self, event: QCloseEvent):
        """
        Handles the application's close event.
        This is triggered by closing the window or by calling self.close().
        It's the central point for cleanup before the application exits.
        """
        self._save_geometry() # From GeometryManagerMixin
        self.controller.handle_application_shutdown()
        super().closeEvent(event)