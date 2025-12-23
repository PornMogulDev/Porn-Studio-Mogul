import logging
from PyQt6.QtCore import QObject, QUrl
from PyQt6.QtGui import QDesktopServices

from utils.paths import ACKNOWLEDGEMENTS_FILE, APP_ROOT

logger = logging.getLogger(__name__)

class StartScreenPresenter(QObject):
    def __init__(self, controller, view, ui_manager, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.view = view
        self.ui_manager = ui_manager

        self._connect_signals()
        self.refresh_state()

    def _connect_signals(self):
        # Controller Signals
        self.controller.signals.saves_changed.connect(self.refresh_state)

        # View Signals
        self.view.continue_clicked.connect(self.controller.continue_game)
        self.view.new_game_clicked.connect(self.controller.new_game_started)
        self.view.quit_clicked.connect(self.controller.quit_game)
        
        self.view.load_clicked.connect(self._on_load_clicked)
        self.view.settings_clicked.connect(self.ui_manager.show_settings_dialog)
        self.view.acknowledgements_clicked.connect(self._on_acknowledgements_clicked)
        
        # Connect the new link handler
        self.view.acknowledgements_link_clicked.connect(self._on_acknowledgements_link_clicked)

    def refresh_state(self):
        has_saves = self.controller.check_for_saves()
        self.view.set_continue_enabled(has_saves)
        self.view.set_load_enabled(has_saves)

    def _on_load_clicked(self):
        self.ui_manager.show_save_load('load')

    def _on_acknowledgements_clicked(self):
        try:
            with open(ACKNOWLEDGEMENTS_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
            self.view.show_acknowledgements_dialog(content)
        except FileNotFoundError:
            logger.error(f"The acknowledgements file could not be found at: {ACKNOWLEDGEMENTS_FILE}")
            self.view.show_acknowledgements_dialog("Error: Acknowledgements file not found.")

    def _on_acknowledgements_link_clicked(self, url: QUrl):
        """
        Handles logic for links clicked inside the acknowledgements dialog.
        Distinguishes between web URLs and local file paths.
        """
        scheme = url.scheme()

        # If it's a web link (http/https), open it directly
        if scheme in ['http', 'https']:
            QDesktopServices.openUrl(url)
            return

        # Handle local files
        path_str = url.toString()
        
        # 1. Clean up "file:" prefix if PyQt added it
        if path_str.startswith("file:"):
            path_str = path_str[5:]
            # Remove leading slashes often added by file:/// on Windows
            if path_str.startswith("///"): 
                path_str = path_str[3:]
        
        # 2. Resolve the path relative to the APP_ROOT
        # In Markdown: [Link](NOTICE.md) -> url is "NOTICE.md"
        # We join APP_ROOT + "NOTICE.md"
        full_path = APP_ROOT / path_str

        logger.debug(f"Opening external file: {full_path}")
        
        # 3. Open the file using the OS default application
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(full_path)))