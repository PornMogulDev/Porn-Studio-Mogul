from PyQt6.QtWidgets import QPushButton, QStyle
from PyQt6.QtCore import pyqtSlot

class HelpButton(QPushButton):
    """
    A standardized help button widget.
    
    This button displays a standard help icon and tooltip. When clicked, it emits
    the controller's global 'show_help_requested' signal with the topic key
    provided during instantiation.
    """
    def __init__(self, topic_key: str, controller, parent=None):
        """
        Args:
            topic_key (str): The unique identifier for the help topic to show.
            controller: The main game controller instance.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.topic_key = topic_key
        self.controller = controller
        self.setFixedSize(24,24)
        
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Sets the visual properties of the button."""
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarContextHelpButton)
        self.setIcon(icon)
        self.setToolTip("Help")

    def _connect_signals(self):
        """Connects the button's clicked signal."""
        self.clicked.connect(self._emit_help_request)

    @pyqtSlot()
    def _emit_help_request(self):
        """Emits the global signal to show the help dialog for this button's topic."""
        self.controller.signals.show_help_requested.emit(self.topic_key)