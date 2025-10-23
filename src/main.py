import sys
from PyQt6.QtWidgets import QApplication
from app.application import ApplicationWindow, apply_theme, handle_exception
from utils.logger_setup import setup_logging
from data.settings_manager import SettingsManager

if __name__ == "__main__":
    # Configure logging as the very first step
    setup_logging()

    sys.excepthook = handle_exception
    app = QApplication(sys.argv)
    main_window = ApplicationWindow()
    main_window.show()
    sys.exit(app.exec())