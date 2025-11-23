import logging
from PyQt6.QtCore import QObject

from utils.paths import ACKNOWLEDGEMENTS_FILE

logger = logging.getLogger(__name__)

class StartScreenPresenter(QObject):
    def __init__(self, controller, view, ui_manager, parent=None):
        """
        Args:
            controller: The GameController
            view: StartScreenView
            ui_manager: UIManager
            parent: Should be the View (StartScreenView) to ensure lifecycle coupling.
        """
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

    def refresh_state(self):
        """Checks for saves and updates the view's button states."""
        has_saves = self.controller.check_for_saves()
        self.view.set_continue_enabled(has_saves)
        self.view.set_load_enabled(has_saves)

    def _on_load_clicked(self):
        self.ui_manager.show_save_load('load')

    def _on_acknowledgements_clicked(self):
        """Reads the markdown file and tells the view to display it."""
        try:
            with open(ACKNOWLEDGEMENTS_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
            self.view.show_acknowledgements_dialog(content)
        except FileNotFoundError:
            logger.error(f"The acknowledgements file could not be found at: {ACKNOWLEDGEMENTS_FILE}")
            self.view.show_acknowledgements_dialog("Error: Acknowledgements file not found.")