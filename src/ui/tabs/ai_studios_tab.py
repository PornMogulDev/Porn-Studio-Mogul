from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter
)
from PyQt6.QtCore import Qt

from ui.widgets.view_menu_button import ViewMenuButton
from ui.widgets.ai_studios.studio_list_widget import StudioListWidget
from ui.widgets.ai_studios.studio_details_widget import StudioDetailsWidget
from ui.widgets.ai_studios.studio_scenes_widget import StudioScenesWidget
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin

class AIStudiosTab(QWidget, GeometryManagerMixin):
    """
    Main tab for viewing AI Studios.
    Uses MVP pattern: Logic is in AIStudiosTabPresenter.
    """
    def __init__(self, theme_manager, settings_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.settings_manager = settings_manager
        self._setup_ui()
        
    def _get_window_name(self) -> str:
        return "AIStudiosTab"

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # --- Toolbar ---
        toolbar_layout = QHBoxLayout()
        self.view_menu_button = ViewMenuButton(self)
        toolbar_layout.addWidget(self.view_menu_button)
        toolbar_layout.addStretch()
        layout.addLayout(toolbar_layout)

        # --- Main Splitter (Horizontal) ---
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left: List
        self.list_widget = StudioListWidget(self.theme_manager)
        self.main_splitter.addWidget(self.list_widget)

        # Right: Details + Scenes (Vertical Splitter)
        self.right_splitter = QSplitter(Qt.Orientation.Vertical)
        
        self.details_widget = StudioDetailsWidget(self.theme_manager)
        self.right_splitter.addWidget(self.details_widget)
        
        self.scenes_widget = StudioScenesWidget(self.theme_manager)
        self.right_splitter.addWidget(self.scenes_widget)
        
        self.main_splitter.addWidget(self.right_splitter)
        
        # Set initial stretch factors (List=1, Details/Scenes=2)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 2)
        
        layout.addWidget(self.main_splitter)

    def set_widget_visibility(self, key: str, visible: bool):
        if key == "list":
            self.list_widget.setVisible(visible)
        elif key == "details":
            self.details_widget.setVisible(visible)
        elif key == "scenes":
            self.scenes_widget.setVisible(visible)