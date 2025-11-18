import logging
from typing import Dict, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QComboBox,
    QDialogButtonBox, QWidget
)

logger = logging.getLogger(__name__)

class SponsorTourDialog(QDialog):
    """
    A dialog for negotiating the terms of a player-sponsored tour.
    """
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
        self._on_accommodation_changed()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.duration_label = QLabel()
        self.destination_label = QLabel()
        self.accommodation_combo = QComboBox()
        self.total_cost_label = QLabel()
        self.total_cost_label.setStyleSheet("font-weight: bold;")

        form_layout.addRow("Talent:", QLabel(self.talent_alias))
        form_layout.addRow("Destination:", self.destination_label)
        form_layout.addRow("Duration:", self.duration_label)
        form_layout.addRow("Accommodation:", self.accommodation_combo)
        form_layout.addRow("Total Upfront Cost:", self.total_cost_label)

        main_layout.addLayout(form_layout)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        main_layout.addWidget(button_box)
        self.ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)

        # Connections for the button box
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

    def _populate_data(self):
        self.duration_label.setText(f"{self.tour_data.get('duration_weeks', 0)} weeks")
        self.destination_label.setText(self.tour_data.get('destination_location', 'N/A'))
        
        required_tier_id = self.tour_data.get('required_accommodation_tier_id')

        for tier in self.tour_data.get('accommodation_options', []):
            display_text = f"{tier['name']} (+${tier['cost_per_week']:,}/week)"
            self.accommodation_combo.addItem(display_text, userData=tier['id'])
            # Disable options that are below the talent's required standard
            if required_tier_id and tier['id'] != required_tier_id:
                if self.tour_data['accommodation_tiers'][tier['id']]['cost_per_week'] < self.tour_data['accommodation_tiers'][required_tier_id]['cost_per_week']:
                    index = self.accommodation_combo.count() - 1
                    self.accommodation_combo.model().item(index).setEnabled(False)

    def _connect_signals(self):
        self.accommodation_combo.currentIndexChanged.connect(self._on_accommodation_changed)

    def _on_accommodation_changed(self):
        """Recalculates and updates the total cost when accommodation changes."""
        accommodation_id = self.accommodation_combo.currentData()
        if not accommodation_id:
            self.ok_button.setEnabled(False)
            return

        self.ok_button.setEnabled(True)
        self.selected_accommodation_id = accommodation_id

        accommodation_tier = self.tour_data['all_accommodation_tiers'].get(accommodation_id)
        if not accommodation_tier:
            return

        duration = self.tour_data.get('duration_weeks', 0)
        travel_cost = self.tour_data.get('travel_cost', 0)
        accommodation_cost = accommodation_tier['cost_per_week'] * duration
        total_cost = travel_cost + accommodation_cost
        self.final_total_cost = total_cost
        
        cost_breakdown = f"(Travel: ${travel_cost:,} + Accommodation: ${accommodation_cost:,})"
        self.total_cost_label.setText(f"${total_cost:,} {cost_breakdown}")

    def get_selected_tour_details(self) -> Optional[Dict]:
        """Returns the final negotiated details of the tour."""
        if self.result() == QDialog.DialogCode.Accepted and self.selected_accommodation_id:
            return {
                "destination_location": self.tour_data.get('destination_location'),
                "start_week": self.tour_data.get('start_week'),
                "start_year": self.tour_data.get('start_year'),
                "duration_weeks": self.tour_data.get('duration_weeks'),
                "accommodation_tier_id": self.selected_accommodation_id
            }
        return None
    
    def get_final_cost(self) -> int:
        """Returns the final calculated upfront cost for the selected tour options."""
        return self.final_total_cost