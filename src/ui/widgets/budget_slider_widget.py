from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QLabel, QSlider, 
                             QSpinBox, QToolButton, QCheckBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon

class BudgetSliderWidget(QWidget):
    """
    A single row representing one department's budget allocation.
    Contains: Name | Slider | Lock | Amount ($) | Estimate Label
    """
    
    # Signal emits (department_id, new_percentage 0.0-1.0)
    allocationChanged = pyqtSignal(str, float)
    lockToggled = pyqtSignal(str, bool)

    def __init__(self, dept_id: str, name: str, parent=None):
        super().__init__(parent)
        self.dept_id = dept_id
        self.name = name
        self._is_updating = False # Prevent feedback loops

        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        # 1. Name Label
        self.lbl_name = QLabel(self.name)
        self.lbl_name.setFixedWidth(100)
        
        # 2. The Slider (0-1000 for 0.1% precision)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.valueChanged.connect(self._on_slider_change)

        # 3. Lock Checkbox (Icon based ideally, simplified for now)
        self.chk_lock = QCheckBox("Lock")
        self.chk_lock.setToolTip("Lock this allocation percentage")
        self.chk_lock.toggled.connect(lambda checked: self.lockToggled.emit(self.dept_id, checked))

        # 4. Amount Display (Read-onlyish, reflects builder state)
        self.lbl_amount = QLabel("$0")
        self.lbl_amount.setFixedWidth(60)
        self.lbl_amount.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # 5. Estimate / Feedback Label
        self.lbl_estimate = QLabel("-")
        self.lbl_estimate.setStyleSheet("color: gray; font-size: 10px;")
        self.lbl_estimate.setFixedWidth(80)

        layout.addWidget(self.lbl_name)
        layout.addWidget(self.slider)
        layout.addWidget(self.chk_lock)
        layout.addWidget(self.lbl_amount)
        layout.addWidget(self.lbl_estimate)

    def update_state(self, percent: float, amount: int, is_locked: bool, estimate_text: str):
        """Updates the widget based on data from the Builder."""
        self._is_updating = True
        
        # Update Slider
        slider_val = int(percent * 1000)
        if self.slider.value() != slider_val:
            self.slider.setValue(slider_val)
            
        # Update Visuals
        self.lbl_amount.setText(f"${amount:,}")
        self.lbl_estimate.setText(estimate_text)
        
        if self.chk_lock.isChecked() != is_locked:
            self.chk_lock.setChecked(is_locked)
            
        # Disable slider if locked
        self.slider.setEnabled(not is_locked)
        
        self._is_updating = False

    def _on_slider_change(self, value):
        if not self._is_updating:
            # Convert 0-1000 back to 0.0-1.0
            float_val = value / 1000.0
            self.allocationChanged.emit(self.dept_id, float_val)