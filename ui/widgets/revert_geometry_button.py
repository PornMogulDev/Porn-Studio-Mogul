from PyQt6.QtWidgets import QPushButton, QStyle

class RestoreGeometryButton(QPushButton):
    """
    A standardized button that reverts its parent widget's geometry.
    
    This button displays a standard reset icon and tooltip. When clicked, it calls the
    'revert_to_initial_geometry' method on its parent widget, which is expected
    to have the GeometryManagerMixin applied.
    """
    def __init__(self, parent=None):
        """
        Args:
            parent: The parent widget. This widget MUST implement the
                    'revert_to_initial_geometry' method (e.g., via GeometryManagerMixin).
        """
        super().__init__(parent)
        self.target_widget = parent
        self.setFixedSize(24,24)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Sets the visual properties of the button."""
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogResetButton)
        self.setIcon(icon)
        self.setToolTip("Revert window position and size to how it was when opened")

    def _connect_signals(self):
        """Connects the button's clicked signal to the parent's method."""
        # Safety check: ensure the parent has the method we want to call.
        if hasattr(self.target_widget, 'revert_to_initial_geometry'):
            self.clicked.connect(self.target_widget.revert_to_initial_geometry)
        else:
            # If the parent is missing the method, disable the button and warn the developer.
            print(f"WARNING: RestoreGeometryButton's parent '{self.target_widget.__class__.__name__}'"
                  " does not have a 'revert_to_initial_geometry' method. The button will be disabled.")
            self.setEnabled(False)