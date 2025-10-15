from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QFrame, QWidget
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

# Forward-declare dataclasses to avoid circular imports, for type hinting only
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from data.game_state import Scene, Talent

from ui.mixins.geometry_manager_mixin import GeometryManagerMixin

class InteractiveEventDialog(GeometryManagerMixin, QDialog):
    """
    A modal dialog that presents a random event to the player and requires
    them to make a choice. The dialog is entirely configured by the event
    data passed to it.
    """
    def __init__(self, event_data: dict, scene_data: 'Scene', talent_data: 'Talent', 
                 current_money: int, controller, parent: QWidget = None):
        super().__init__(parent)
        
        self.event_data = event_data
        self.scene_data = scene_data
        self.talent_data = talent_data
        self.current_money = current_money
        self.controller = controller
        self.settings_manager = self.controller.settings_manager
        
        # This will store the 'id' of the choice the player makes
        self.selected_choice_id = None

        self.setWindowTitle(self.event_data.get('name', 'An Event Occurs'))
        self.setModal(True)
        self.setMinimumWidth(450)
        
        # Prevent the user from closing the dialog without making a choice
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)
        
        self.setup_ui()

        self._restore_geometry()

    def _format_text(self, text: str) -> str:
        """Replaces placeholders in a string with context-specific data."""
        if self.talent_data:
            text = text.replace('{talent_name}', f"<b>{self.talent_data.alias}</b>")
        if self.scene_data:
            text = text.replace('{scene_title}', f"<i>{self.scene_data.title}</i>")
        return text

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Event Title ---
        title_label = QLabel(self._format_text(self.event_data.get('name', '')))
        font = title_label.font()
        font.setPointSize(14)
        font.setBold(True)
        title_label.setFont(font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        # --- Event Description ---
        description_label = QLabel(self._format_text(self.event_data.get('description', '')))
        description_label.setWordWrap(True)
        main_layout.addWidget(description_label)
        
        # --- Separator ---
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line)

        # --- Dynamic Choice Buttons ---
        choices = self.event_data.get('choices', [])
        if not choices:
            # Fallback in case of bad data, so the UI doesn't lock up
            fallback_button = QPushButton("Acknowledge")
            fallback_button.clicked.connect(self.accept)
            main_layout.addWidget(fallback_button)
        else:
            for choice in choices:
                button = self._create_choice_button(choice)
                main_layout.addWidget(button)

    def _create_choice_button(self, choice_data: dict) -> QPushButton:
        """Creates a single button for a given choice dictionary."""
        button_text = self._format_text(choice_data.get('text', '...'))
        button = QPushButton(button_text)
        
        if hint := choice_data.get('hint'):
            button.setToolTip(self._format_text(hint))
        
        # Check if the choice is available based on requirements
        is_enabled, reason = self._check_requirements(choice_data.get('requirements'))
        button.setEnabled(is_enabled)
        if not is_enabled:
            button.setToolTip(f"{button.toolTip()}\n\nDisabled: {reason}")
            
        # Connect the button click to our handler
        choice_id = choice_data.get('id')
        if choice_id:
            button.clicked.connect(lambda: self._on_choice_selected(choice_id))
            
        return button

    def _check_requirements(self, requirements: list | None) -> tuple[bool, str]:
        """
        Validates if the player meets the requirements for a choice.
        Returns a tuple: (is_met, reason_if_not_met).
        """
        if not requirements:
            return True, ""
            
        for req in requirements:
            req_type = req.get('type')
            if req_type == 'has_money':
                amount_needed = req.get('amount', 0)
                if self.current_money < amount_needed:
                    return False, f"Not enough money. Need ${amount_needed:,}, have ${self.current_money:,}."
            # Future requirement types (e.g., 'has_item', 'skill_check') can be added here
        
        return True, ""

    def _on_choice_selected(self, choice_id: str):
        """Stores the selected choice ID and closes the dialog."""
        self.selected_choice_id = choice_id
        self.accept()