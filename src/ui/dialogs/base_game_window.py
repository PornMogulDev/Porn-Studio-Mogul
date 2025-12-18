from PyQt6.QtWidgets import QDialog
from PyQt6.QtCore import Qt
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin

class BaseGameWindow(GeometryManagerMixin, QDialog):
    """
    Standard base class for modeless game windows (like Roster, Scene Planner).
    
    Features:
    - Automatic geometry saving/restoring via GeometryManagerMixin
    - Standard window flags (Minimize, Maximize, Close)
    - DeleteOnClose attribute set by default
    
    Usage:
    class MyWindow(BaseGameWindow):
        def __init__(self, settings_manager, parent=None):
            super().__init__(settings_manager, parent)
            self.setup_ui()
    """
    def __init__(self, settings_manager, parent=None):
        # Initialize QDialog
        super().__init__(parent)
        
        # Store settings manager (required by GeometryManagerMixin)
        self.settings_manager = settings_manager
        
        # Set standard window flags for a standalone tool window
        self.setWindowFlags(
            Qt.WindowType.Window | 
            Qt.WindowType.WindowMinMaxButtonsHint | 
            Qt.WindowType.WindowCloseButtonHint
        )
        
        # Ensure the widget is deleted when closed to trigger cleanup signals
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        
        # Restore geometry from settings (GeometryManagerMixin)
        # Note: subclasses usually call this at the END of their __init__ 
        # to ensure sizeHint is accurate, but we call it here to ensure 
        # it's not forgotten. If sizeHint depends on content, subclasses 
        # can call self._restore_geometry() again after setup.
        self._restore_geometry()

    def set_presenter(self, presenter):
        """
        Standard method to attach a presenter. 
        Keeps a reference to prevent garbage collection.
        """
        self.presenter = presenter