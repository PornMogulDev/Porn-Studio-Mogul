import logging
from typing import Dict, Optional
from PyQt6.QtCore import QCoreApplication, pyqtSignal
from PyQt6.QtWidgets import (
     QDialog, QVBoxLayout, QFormLayout, QLabel, QComboBox,
     QDialogButtonBox, QWidget, QSpinBox
)

from utils import time_utils

logger = logging.getLogger(__name__)

class SponsorTourDialog(QDialog):
    """
    A dialog for negotiating the terms of a player-sponsored tour.
    """

    # Emitted when the user clicks OK, before the dialog closes, to allow for processing.
    tour_confirmed = pyqtSignal()

    def __init__(self, talent_alias: str, tour_data: Dict, parent: QWidget = None):
        super().__init__(parent)
        self.talent_alias = talent_alias
        self.tour_data = tour_data
        self.selected_accommodation_id: Optional[str] = None
        self.final_total_cost: int = 0
        
        self.setWindowTitle(f"Sponsor Tour for {self.talent_alias}")
        self.setMinimumWidth(400)

        self._setup_ui()
        self._populate_data()
        self._connect_signals()

        # Set initial selection and update costs
        if self.accommodation_combo.count() > 0:
            if required_tier_id := self.tour_data.get('required_accommodation_tier_id'):
                index = self.accommodation_combo.findData(required_tier_id)
                if index != -1:
                    self.accommodation_combo.setCurrentIndex(index)
                else: # Fallback if required tier is somehow not in the options
                    self.accommodation_combo.setCurrentIndex(0)
            else:
                 self.accommodation_combo.setCurrentIndex(0)
        self._update_costs()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.duration_label = QLabel()
        self.destination_label = QLabel()
        self.duration_spinbox = QSpinBox()
        self.duration_spinbox.setSuffix(" weeks")
        self.accommodation_combo = QComboBox()
        self.character_comment_label = QLabel()
        self.character_comment_label.setObjectName("characterComment") # For QSS styling
        self.total_cost_label = QLabel()
        self.total_cost_label.setStyleSheet("font-weight: bold;")

        form_layout.addRow("Talent:", QLabel(self.talent_alias))
        form_layout.addRow("Destination:", self.destination_label)
        form_layout.addRow("Duration:", self.duration_spinbox)
        form_layout.addRow("Accommodation:", self.accommodation_combo)
        form_layout.addRow("", self.character_comment_label)
        form_layout.addRow("Total Upfront Cost:", self.total_cost_label)

        main_layout.addLayout(form_layout)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        main_layout.addWidget(button_box)
        self.ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)

        # Connections
        # We handle OK manually to show a "Processing" state
        self.ok_button.clicked.connect(self._on_confirm_clicked)
        button_box.rejected.connect(self.reject)

    def _populate_data(self):
        self.destination_label.setText(self.tour_data.get('destination_location', 'N/A'))
        
        # Set up duration spinbox
        min_duration = self.tour_data.get('minimum_duration_weeks', 1)
        self.duration_spinbox.setRange(min_duration, 4)
        self.duration_spinbox.setValue(min_duration)

        # Populate all accommodation tiers and disable unacceptable ones
        required_tier_id = self.tour_data.get('required_accommodation_tier_id')
        all_tiers = self.tour_data.get('all_accommodation_tiers', {})
        required_tier_cost = all_tiers.get(required_tier_id, {}).get('cost_per_week', 0)

        for tier_id, tier in all_tiers.items():
            display_text = f"{tier['name']} (+${tier['cost_per_week']:,}/week)"
            self.accommodation_combo.addItem(display_text, userData=tier_id)

            if tier['cost_per_week'] < required_tier_cost:
                index = self.accommodation_combo.count() - 1
                self.accommodation_combo.model().item(index).setEnabled(False)
        
        if required_tier_name := all_tiers.get(required_tier_id, {}).get('name'):
            self.character_comment_label.setText(f"\"{required_tier_name} is the least I will accept.\"")

    def _connect_signals(self):
        self.accommodation_combo.currentIndexChanged.connect(self._update_costs)
        self.duration_spinbox.valueChanged.connect(self._update_costs)

    def _update_costs(self):
        """Recalculates and updates the total cost when accommodation changes."""
        accommodation_id = self.accommodation_combo.currentData()
        duration = self.duration_spinbox.value()
        if not accommodation_id:
            self.ok_button.setEnabled(False)
            return

        self.selected_accommodation_id = accommodation_id

        accommodation_tier = self.tour_data.get('all_accommodation_tiers', {}).get(accommodation_id)
        if not accommodation_tier:
            return

        travel_cost = self.tour_data.get('travel_cost', 0)
        accommodation_cost = accommodation_tier['cost_per_week'] * duration
        total_cost = travel_cost + accommodation_cost
        self.final_total_cost = total_cost
        
        cost_breakdown = f"(Travel: ${travel_cost:,} + Accommodation: ${accommodation_cost:,})"
        self.total_cost_label.setText(f"${total_cost:,} {cost_breakdown}")

    def _on_confirm_clicked(self):
        """
        Updates UI to show processing state, executes logic, then closes.
        """
        if not self.selected_accommodation_id:
            return

        # 1. Update UI to show busy state
        self.ok_button.setEnabled(False)
        self.duration_spinbox.setEnabled(False)
        self.accommodation_combo.setEnabled(False)
        self.total_cost_label.setText("Finalizing tour details... This may take a moment.")
        self.total_cost_label.setStyleSheet("color: #2980b9; font-weight: bold;") # Use a visible color (blue-ish)
        
        # 2. Force the UI to repaint so the user sees the message
        QCoreApplication.processEvents()

        # 3. Emit signal to trigger the heavy synchronous work in the Controller
        self.tour_confirmed.emit()

        # 4. Work is done, close the dialog
        self.accept()

    def get_selected_tour_details(self) -> Optional[Dict]:
        """Returns the final negotiated details of the tour."""
        if self.selected_accommodation_id:

            # Convert the UI-friendly start date back to absolute week for the database
            start_year = self.tour_data.get('start_year')
            start_week = self.tour_data.get('start_week')
            start_absolute_week = time_utils.to_absolute(start_year, start_week)

            return {
                "destination_location": self.tour_data.get('destination_location'),
                "start_absolute_week": start_absolute_week,
                "duration_weeks": self.duration_spinbox.value(),
                "accommodation_tier_id": self.selected_accommodation_id
            }
        return None
    
    def get_final_cost(self) -> int:
        """Returns the final calculated upfront cost for the selected tour options."""
        return self.final_total_cost