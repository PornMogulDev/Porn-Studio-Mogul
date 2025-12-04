from PyQt6.QtWidgets import QToolButton
from PyQt6.QtCore import pyqtSlot, pyqtSignal

from ui.managers.icon_manager import IconManager


class HelpButton(QToolButton):
    """
    A standardized help button widget that uses the application's IconManager.
    
    This button displays a standard help icon and tooltip. When clicked, it emits
    the controller's global 'show_help_requested' signal with the topic key
    provided during instantiation.
    """
    help_requested = pyqtSignal(str)

    def __init__(self, topic_key: str, icon_manager: IconManager, parent=None):
        """
        Args:
            topic_key (str): The unique identifier for the help topic to show.
            icon_manager (IconManager): The manager for styling icons.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.topic_key = topic_key
        self.icon_manager = icon_manager
        
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Sets the visual properties of the button."""
        self.icon_manager.apply_icon(self, "help_icon", "accent")
        self.setToolTip("Help")

    def _connect_signals(self):
        """Connects the button's clicked signal."""
        self.clicked.connect(self._emit_help_request)

    def refresh_icon(self):
        """Makes sure the icon keeps up with changes to theme/font size."""
        self.icon_manager.apply_icon(self, "help_icon", "accent")

    @pyqtSlot()
    def _emit_help_request(self):
        """Emits a signal to request help for this button's topic."""
        self.help_requested.emit(self.topic_key)