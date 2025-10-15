import sys
from PyQt6.QtWidgets import QApplication
from app.application import ApplicationWindow, apply_theme, handle_exception
from utils.logger_setup import setup_logging
from data.settings_manager import SettingsManager

if __name__ == "__main__":
    # Configure logging as the very first step
    setup_logging()

    # --- Debugger Setup ---
    # Start the debugpy server to allow remote debugging.
    import debugpy
    debugpy.listen(5678)
    print("⏳ Waiting for debugger to attach...")
    debugpy.wait_for_client()
    print("✅ Debugger attached.")
    # --- End Debugger Setup ---

    sys.excepthook = handle_exception
    app = QApplication(sys.argv)

    settings = SettingsManager()
    apply_theme(settings)
    
    window = ApplicationWindow()
    window.show()
    sys.exit(app.exec())