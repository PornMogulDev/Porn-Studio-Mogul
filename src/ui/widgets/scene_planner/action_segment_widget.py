from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QSpinBox, QLabel

from data.game_state import ActionSegment

class ActionSegmentItemWidget(QWidget):
    parameter_changed = pyqtSignal(int, str, int)
    def __init__(self, segment: ActionSegment, tag_def: dict, parent=None):
        super().__init__(parent); self.segment = segment; self.tag_def = tag_def
        self.setup_ui()
    def setup_ui(self):
        layout = QHBoxLayout(self); layout.setContentsMargins(4, 2, 4, 2)
        param_text = []
        for role, value in self.segment.parameters.items():
            param_text.append(f"{value} {role}(s)")
        label_text = f"{self.segment.tag_name} ({self.segment.runtime_percentage}%)"
        if param_text: label_text += f" [{', '.join(param_text)}]"
        layout.addWidget(QLabel(label_text), 1)
        for slot in self.tag_def.get("slots", []):
            if "parameterized_by" in slot and slot["parameterized_by"] == "count":
                role = slot['role']; spinbox = QSpinBox()
                spinbox.setRange(slot.get('min_count', 1), slot.get('max_count', 10))
                spinbox.setValue(self.segment.parameters.get(role, 1))
                spinbox.valueChanged.connect(lambda val, r=role: self.parameter_changed.emit(self.segment.id, r, val))
                layout.addWidget(QLabel(f"{role}s:"))
                layout.addWidget(spinbox)