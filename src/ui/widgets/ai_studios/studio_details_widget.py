from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel, QGroupBox
)
from PyQt6.QtCore import Qt
from data.game_state import AIStudio

class StudioDetailsWidget(QWidget):
    """
    Displays detailed information about a selected AI Studio.
    """
    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.group_box = QGroupBox("Studio Details")
        form_layout = QFormLayout(self.group_box)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.name_label = QLabel("-")
        self.location_label = QLabel("-")
        self.money_label = QLabel("-")
        self.status_label = QLabel("-")
        self.target_label = QLabel("-")
        self.markets_label = QLabel("-")
        self.markets_label.setWordWrap(True)

        form_layout.addRow("Name:", self.name_label)
        form_layout.addRow("Location:", self.location_label)
        form_layout.addRow("Funds:", self.money_label)
        form_layout.addRow("Status:", self.status_label)
        form_layout.addRow("Monthly Target:", self.target_label)
        form_layout.addRow("Preferred Markets:", self.markets_label)

        layout.addWidget(self.group_box)

    def display_studio(self, studio: AIStudio):
        self.name_label.setText(studio.name)
        self.location_label.setText(studio.location)
        self.money_label.setText(f"${studio.money:,}")
        self.status_label.setText("Active" if studio.active else "Inactive")
        self.target_label.setText(f"{studio.scenes_per_month_target} scenes")
        self.markets_label.setText(", ".join(studio.preferred_market_groups) if studio.preferred_market_groups else "None")

    def clear(self):
        self.name_label.setText("-")
        self.location_label.setText("-")
        self.money_label.setText("-")
        self.status_label.setText("-")
        self.target_label.setText("-")
        self.markets_label.setText("-")