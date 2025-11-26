from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QLabel, QSlider, 
                             QCheckBox, QComboBox)
from PyQt6.QtCore import Qt, pyqtSignal

class BudgetSliderWidget(QWidget):
    """
    A single row representing one department's budget allocation.
    """
    
    # Signal emits (department_id, new_percentage 0.0-1.0)
    allocationChanged = pyqtSignal(str, float)
    lockToggled = pyqtSignal(str, bool)

    def __init__(self, dept_id: str, name: str, parent=None, show_assignment: bool = False):
        super().__init__(parent)
        self.dept_id = dept_id
        self.name = name
        self.show_assignment = show_assignment
        
        self._is_updating = False # Critical for preventing feedback loops

        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        # 1. Name Label
        self.lbl_name = QLabel(self.name)
        self.lbl_name.setFixedWidth(110)

        # 2. Assignment Selector (Optional)
        if self.show_assignment:
            self.combo_assignment = QComboBox()
            self.combo_assignment.addItems(["Generic / Freelancer"])
            self.combo_assignment.setEnabled(False) # Placeholder
            self.combo_assignment.setFixedWidth(130)
        
        # 3. The Slider (0-1000 for 0.1% precision)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.valueChanged.connect(self._on_slider_change)

        # 4. Lock Checkbox
        self.chk_lock = QCheckBox("Lock")
        self.chk_lock.setToolTip("Lock this allocation percentage")
        self.chk_lock.toggled.connect(self._on_lock_toggled)

        # 5. Amount Display
        self.lbl_amount = QLabel("$0")
        self.lbl_amount.setFixedWidth(60)
        self.lbl_amount.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # 6. Estimate / Feedback Label
        self.lbl_estimate = QLabel("-")
        self.lbl_estimate.setStyleSheet("color: gray; font-size: 10px;")
        self.lbl_estimate.setFixedWidth(80)

        layout.addWidget(self.lbl_name)
        if self.show_assignment:
            layout.addWidget(self.combo_assignment)
        layout.addWidget(self.slider)
        layout.addWidget(self.chk_lock)
        layout.addWidget(self.lbl_amount)
        layout.addWidget(self.lbl_estimate)

    def update_state(self, percent: float, amount: int, is_user_locked: bool, is_system_disabled: bool, estimate_text: str):
        """Updates the widget based on data from the Builder."""
        self._is_updating = True
        
        # 1. Update Slider
        new_slider_val = int(percent * 1000)
        if self.slider.value() != new_slider_val:
            self.slider.setValue(new_slider_val)
            
        # 2. Update Visuals
        self.lbl_amount.setText(f"${amount:,}")
        self.lbl_estimate.setText(estimate_text)
        
        # 3. Handle Disabled State (System Logic)
        if is_system_disabled:
            self.setEnabled(False)
            self.chk_lock.setChecked(True) # Visually show it's fixed
            self.lbl_estimate.setText("Not Required")
        else:
            self.setEnabled(True)
            # 4. Handle Lock State (User Logic)
            if self.chk_lock.isChecked() != is_user_locked:
                self.chk_lock.setChecked(is_user_locked)
            
            # Only the slider is disabled when user-locked, not the whole widget
            self.slider.setEnabled(not is_user_locked)
            # Cannot lock a 0% slider usually, or leave it enabled
            self.chk_lock.setEnabled(True) 

        self._is_updating = False

    def _on_slider_change(self, value):
        if not self._is_updating:
            float_val = value / 1000.0
            self.allocationChanged.emit(self.dept_id, float_val)

    def _on_lock_toggled(self, checked):
        if not self._is_updating:
            self.lockToggled.emit(self.dept_id, checked)