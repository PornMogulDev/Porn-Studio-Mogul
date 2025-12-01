from PyQt6.QtWidgets import QWidget, QVBoxLayout, QFrame
from PyQt6.QtCore import Qt
from ui.widgets.talent_profile.details_widget import DetailsWidget
from ui.builders.talent_view_data_builder import TalentViewDataBuilder
from data.game_state import Talent

class EntitySummaryCard(QWidget):
    """
    A floating tooltip-like widget that displays a summary of an entity.
    Reuses the DetailsWidget to show talent info.
    """
    def __init__(self, settings_manager, parent=None):
        # ToolTip flag makes it float above other windows, Frameless removes OS window chrome
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        # Main Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Container frame for styling (border, background) to mimic a card
        self.container = QFrame()
        self.container.setObjectName("SummaryCard")
        # Inline style for basic visibility, should be moved to theme manager ideally
        self.container.setStyleSheet("""
            QFrame#SummaryCard {
                background-color: #2b2b2b;
                border: 1px solid #555;
                border-radius: 4px;
            }
        """)
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(5, 5, 5, 5)
        
        # Reuse existing details widget
        self.details_widget = DetailsWidget(settings_manager)
        # Hide the physical attributes row by default in summary to save space if needed, 
        # or keep it if detail is preferred.
        
        container_layout.addWidget(self.details_widget)
        
        layout.addWidget(self.container)

    def load_talent(self, talent: Talent, controller):
        """Populates the internal details widget using the shared builder."""
        basic_info = TalentViewDataBuilder.build_basic_info(talent, controller)
        skills_info = TalentViewDataBuilder.build_skills_info(talent)
        
        self.details_widget.display_basic_info(basic_info)
        self.details_widget.display_skills(skills_info)
        self.details_widget.populate_physical_label(talent)
        
        # Force a layout update and resize to fit content tightly
        self.adjustSize()