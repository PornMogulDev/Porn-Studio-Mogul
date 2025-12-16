from typing import List, Optional
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QComboBox, QLabel

class SlotAssignmentWidget(QWidget):
    assignment_changed = pyqtSignal(int, str, str, object) # segment_id, slot_id, role, vp_id

    def __init__(self, segment_id: int, slot_id: str, slot_def: dict, effective_gender_req: str = None, parent=None):
        super().__init__(parent)
        self.segment_id = segment_id
        self.slot_id = slot_id
        self.slot_def = slot_def
        # Use the override if provided, otherwise fall back to the static definition
        self.display_gender = effective_gender_req if effective_gender_req else slot_def.get('gender', 'Any')
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        
        # Use the determined display gender
        label_text = f"<b>{self.slot_def['role']}</b> (Requires: {self.display_gender})"
        
        layout.addWidget(QLabel(label_text))
        self.performer_combo = QComboBox()
        layout.addWidget(self.performer_combo)
        self.performer_combo.currentIndexChanged.connect(self._on_selection_change)

    def update_options(self, options: List[tuple], current_vp_id: Optional[int]):
        self.performer_combo.blockSignals(True)
        self.performer_combo.clear()
        self.performer_combo.addItem("Unassigned", -1)
        for display_name, vp_id in options:
            self.performer_combo.addItem(display_name, vp_id)

        index = self.performer_combo.findData(current_vp_id)
        self.performer_combo.setCurrentIndex(index if index != -1 else 0)
        self.performer_combo.blockSignals(False)

    def _on_selection_change(self):
        vp_id = self.performer_combo.currentData()
        self.assignment_changed.emit(self.segment_id, self.slot_id, self.slot_def['role'], vp_id if vp_id != -1 else None)