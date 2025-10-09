import os, sys, traceback
from datetime import datetime
from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QMessageBox
from PyQt6.QtCore import pyqtSlot
import qdarktheme

from data_manager import DataManager
from game_controller import GameController
from start_screen import MenuScreen
from main_window import MainGameWindow
from settings_manager import SettingsManager 
from game_strings import game_name
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin

def handle_exception(exc_type, exc_value, exc_traceback):
    """
    Catches unhandled exceptions, logs them to a file, and shows a user-friendly dialog.
    """
    # 1. Format the traceback
    error_message = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    
    # 2. Create a timestamped log file
    log_dir = "crash_logs"
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file_path = os.path.join(log_dir, f"crash_{timestamp}.log")
    
    # 3. Write the error to the log file
    log_content = f"--- CRASH REPORT ---\n"
    log_content += f"Timestamp: {timestamp}\n\n"
    log_content += error_message
    
    try:
        with open(log_file_path, "w") as f:
            f.write(log_content)
    except Exception as e:
        print(f"CRITICAL: Failed to write crash log: {e}")

    sys.excepthook = sys.__excepthook__

    # 4. Display a message to the user
    # We must create a temporary QApplication if the main one has already crashed.
    # If the app hasn't been created yet, this is also safe.
    if not QApplication.instance():
        _ = QApplication([])

    error_dialog = QMessageBox()
    error_dialog.setIcon(QMessageBox.Icon.Critical)
    error_dialog.setText("A critical error occurred.")
    error_dialog.setInformativeText(
        f"The application has experienced some kind of bug. A detailed traceback has been saved to:\n\n"
        f"{os.path.abspath(log_file_path)}\n\n"
        "Please, provide this file alongside your bug report. Thank you."
    )
    error_dialog.setWindowTitle("Application Error")
    error_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
    error_dialog.exec()

    # 5. Call the default excepthook to exit the program
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

def apply_theme(settings_manager: SettingsManager):
    """Reads the theme from settings and applies it to the application."""
    theme_name = settings_manager.get_setting("theme", "system")
    app = QApplication.instance()
    if not app:
        return
        
    if theme_name == "system":
        # An empty stylesheet reverts to the default system style
        app.setStyleSheet("")
    else:
        try:
            app.setStyleSheet(qdarktheme.load_stylesheet(theme_name))
        except TypeError:
            # Fallback if an invalid theme name is somehow in settings.json
            print(f"Warning: Invalid theme '{theme_name}' in settings. Reverting to system default.")
            app.setStyleSheet("")


class ApplicationWindow(QMainWindow, GeometryManagerMixin):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(game_name)
        self.setMinimumSize(1366, 768)

        self.settings_manager = SettingsManager()
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
        if key == "theme":
            apply_theme(self.settings_manager)


if __name__ == "__main__":
    sys.excepthook = handle_exception
    app = QApplication(sys.argv)

    settings = SettingsManager()
    apply_theme(settings)
    
    window = ApplicationWindow()
    window.show()
    sys.exit(app.exec())