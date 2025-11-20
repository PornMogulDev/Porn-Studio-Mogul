from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QLabel,
    QPushButton, QHBoxLayout, QFormLayout, QSpinBox, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal

class TourPage(QWidget):
    """Form for defining details of a sponsored tour."""
    
    confirm_tour_requested = pyqtSignal(dict) # {duration, accommodation_id, total_cost}
    cancel_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tour_data = {}
        self._selected_accommodation_id = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        grp = QGroupBox("Sponsor Tour Details")
        form = QFormLayout(grp)

        self.destination_label = QLabel("N/A")
        form.addRow("Destination:", self.destination_label)
        
        self.duration_spin = QSpinBox()
        self.duration_spin.setSuffix(" weeks")
        self.duration_spin.setRange(1, 4)
        self.duration_spin.valueChanged.connect(self._recalc_cost)
        form.addRow("Duration:", self.duration_spin)

        self.accommodation_combo = QComboBox()
        self.accommodation_combo.currentIndexChanged.connect(self._recalc_cost)
        form.addRow("Accommodation:", self.accommodation_combo)

        self.comment_label = QLabel()
        self.comment_label.setStyleSheet("font-style: italic; color: #555;")
        self.comment_label.setWordWrap(True)
        form.addRow("", self.comment_label)

        layout.addWidget(grp)

        self.cost_label = QLabel("Total: $0")
        self.cost_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cost_label.setStyleSheet("font-weight: bold; font-size: 14px; margin: 10px 0;")
        layout.addWidget(self.cost_label)
        
        layout.addStretch() # Push buttons to bottom

        btns = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_confirm = QPushButton("Confirm Tour Sponsorship")
        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_confirm)
        layout.addLayout(btns)

        self.btn_cancel.clicked.connect(self.cancel_clicked)
        self.btn_confirm.clicked.connect(self._on_confirm)

    def populate(self, tour_data: dict):
        """Loads data into the form."""
        self._tour_data = tour_data
        self.destination_label.setText(tour_data.get('destination_location', 'Unknown'))
        
        min_duration = tour_data.get('minimum_duration_weeks', 1)
        self.duration_spin.setRange(min_duration, 4)
        self.duration_spin.setValue(min_duration)

        # Accommodation
        self.accommodation_combo.blockSignals(True)
        self.accommodation_combo.clear()
        
        required_tier_id = tour_data.get('required_accommodation_tier_id')
        all_tiers = tour_data.get('all_accommodation_tiers', {})
        required_tier_cost = all_tiers.get(required_tier_id, {}).get('cost_per_week', 0)

        for tier_id, tier in all_tiers.items():
            display_text = f"{tier['name']} (+${tier['cost_per_week']:,}/week)"
            self.accommodation_combo.addItem(display_text, userData=tier_id)

            # Disable tiers below requirement
            if tier['cost_per_week'] < required_tier_cost:
                idx = self.accommodation_combo.count() - 1
                self.accommodation_combo.model().item(idx).setEnabled(False)

        # Select required tier by default
        if required_tier_id:
            idx = self.accommodation_combo.findData(required_tier_id)
            if idx >= 0:
                self.accommodation_combo.setCurrentIndex(idx)
                req_name = all_tiers[required_tier_id]['name']
                self.comment_label.setText(f"\"{req_name} is the least I will accept.\"")
            else:
                self.comment_label.setText("")
        
        self.accommodation_combo.blockSignals(False)
        self._recalc_cost()

    def _recalc_cost(self):
        tier_id = self.accommodation_combo.currentData()
        self._selected_accommodation_id = tier_id
        
        if not tier_id or not self._tour_data:
            self.cost_label.setText("Total: --")
            self.btn_confirm.setEnabled(False)
            return

        tiers = self._tour_data.get('all_accommodation_tiers', {})
        if tier_id not in tiers: return

        weeks = self.duration_spin.value()
        acc_cost_per_week = tiers[tier_id]['cost_per_week']
        travel_cost = self._tour_data.get('travel_cost', 0)
        
        total = travel_cost + (acc_cost_per_week * weeks)
        
        self.cost_label.setText(f"Total: ${total:,} (Travel: ${travel_cost:,} + Acc: ${acc_cost_per_week*weeks:,})")
        self.btn_confirm.setEnabled(True)

    def _on_confirm(self):
        if not self._selected_accommodation_id: return
        
        # Re-calculate strictly to send back clean data
        weeks = self.duration_spin.value()
        tiers = self._tour_data.get('all_accommodation_tiers', {})
        acc_cost = tiers[self._selected_accommodation_id]['cost_per_week'] * weeks
        travel_cost = self._tour_data.get('travel_cost', 0)

        payload = {
            "destination_location": self._tour_data.get('destination_location'),
            "start_week": self._tour_data.get('start_week'),
            "start_year": self._tour_data.get('start_year'),
            "duration_weeks": weeks,
            "accommodation_tier_id": self._selected_accommodation_id,
            "total_cost": travel_cost + acc_cost
        }
        self.confirm_tour_requested.emit(payload)