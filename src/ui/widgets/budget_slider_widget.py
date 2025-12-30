from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QSlider, 
                             QToolButton, QComboBox)
from PyQt6.QtCore import Qt, pyqtSignal, QSize

from ui.managers.icon_manager import IconManager

class BudgetSliderWidget(QWidget):
    """
    A two-row widget representing one department's budget allocation.
    Top Row: Name, Amount, Percentage, Estimate
    Bottom Row: (Assignment), Slider, Lock
    """
    
    # Signal emits (department_id, new_percentage 0.0-1.0)
    allocationChanged = pyqtSignal(str, float)
    lockToggled = pyqtSignal(str, bool)

    def __init__(self, dept_id: str, name: str, icon_manager: IconManager,
                 parent=None, show_assignment: bool = False):
        super().__init__(parent)
        self.dept_id = dept_id
        self.name = name
        self.icon_manager = icon_manager
        self.show_assignment = show_assignment
        
        self._is_updating = False # Critical for preventing feedback loops

        self._setup_ui()

    def _setup_ui(self):
        # Main Vertical Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 8) # Little padding bottom for separation
        layout.setSpacing(2) # Keep top and bottom rows tight

        # --- Top Row: Info ---
        top_layout = QHBoxLayout()
        top_layout.setSpacing(10)
        top_layout.setContentsMargins(0, 0, 0, 0)

        # 1. Name Label
        self.lbl_name = QLabel(self.name)
        self.lbl_name.setStyleSheet("font-weight: bold;")
        
        # 2. Amount Display
        self.lbl_amount = QLabel("$0")
        self.lbl_amount.setFixedWidth(70)
        self.lbl_amount.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_amount.setStyleSheet("color: #2c3e50;")

        # 3. Percentage Display (New)
        self.lbl_percent = QLabel("0.0%")
        self.lbl_percent.setFixedWidth(50)
        self.lbl_percent.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # 4. Estimate / Feedback Label
        self.lbl_estimate = QLabel("-")
        self.lbl_estimate.setStyleSheet("color: gray; font-size: 11px;")
        self.lbl_estimate.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_estimate.setFixedWidth(90) # Fixed width prevents jitter

        # Assemble Top Row
        top_layout.addWidget(self.lbl_name)
        top_layout.addStretch() # Push numbers to the right
        top_layout.addWidget(self.lbl_amount)
        top_layout.addWidget(self.lbl_percent)
        top_layout.addWidget(self.lbl_estimate)

        # --- Bottom Row: Controls ---
        bot_layout = QHBoxLayout()
        bot_layout.setSpacing(8)
        bot_layout.setContentsMargins(0, 0, 0, 0)

        # 5. Assignment Selector (Optional)
        if self.show_assignment:
            self.combo_assignment = QComboBox()
            self.combo_assignment.addItems(["Generic / Freelancer"])
            self.combo_assignment.setEnabled(False) # Placeholder
            self.combo_assignment.setFixedWidth(120)
            bot_layout.addWidget(self.combo_assignment)

        # 6. The Slider (0-1000 for 0.1% precision)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.valueChanged.connect(self._on_slider_change)
        bot_layout.addWidget(self.slider)

        # Lock Button
        self.btn_lock = QToolButton()
        self.btn_lock.setCheckable(True)
        self.btn_lock.setIconSize(QSize(16, 16))
        self.btn_lock.setToolTip("Lock this allocation percentage")
        self.btn_lock.toggled.connect(self._on_lock_toggled)
        
        # Initial Icon (Unlocked, Normal Color)
        self.icon_manager.apply_icon(self.btn_lock, "unlocked_icon", "accent")
        
        bot_layout.addWidget(self.btn_lock)
        
        # Add rows to main layout
        layout.addLayout(top_layout)
        layout.addLayout(bot_layout)

    def update_state(self, percent: float, amount: int, is_user_locked: bool, is_system_disabled: bool, estimate_text: str):
        """Updates the widget based on data from the Builder."""
        self._is_updating = True
        
        # 1. Update Slider
        new_slider_val = int(percent * 1000)
        if self.slider.value() != new_slider_val:
            self.slider.setValue(new_slider_val)
            
        # 2. Update Visuals
        self.lbl_amount.setText(f"${amount:,}")
        self.lbl_percent.setText(f"{percent * 100:.1f}%")
        self.lbl_estimate.setText(estimate_text)
        
        # 3. Handle Disabled State
        if is_system_disabled:
            self.slider.setEnabled(False)
            self.btn_lock.setEnabled(False)
            self.btn_lock.setChecked(True) 
            
            # System Disabled: Locked Icon + Disabled Color
            self.icon_manager.apply_icon(self.btn_lock, "locked_icon", "disabled")
            
            self.lbl_estimate.setText("Not Required")
            self.setStyleSheet("color: gray;")
        else:
            self.setStyleSheet("")
            if self.btn_lock.isChecked() != is_user_locked:
                self.btn_lock.setChecked(is_user_locked)

            # --- DECOUPLED LOGIC ---
            if is_user_locked:
                # User Locked: Locked Icon + Disabled Color (Gray)
                self.icon_manager.apply_icon(self.btn_lock, "locked_icon", "disabled")
            else:
                # Unlocked: Unlocked Icon + Text Color (Normal)
                self.icon_manager.apply_icon(self.btn_lock, "unlocked_icon", "accent")
            
            self.slider.setEnabled(not is_user_locked)
            self.btn_lock.setEnabled(True) 

        self._is_updating = False

    def _on_slider_change(self, value):
        if not self._is_updating:
            float_val = value / 1000.0
            # Update local label immediately for responsiveness
            self.lbl_percent.setText(f"{float_val * 100:.1f}%")
            self.allocationChanged.emit(self.dept_id, float_val)

    def _on_lock_toggled(self, checked):
        if not self._is_updating:
            # Immediate feedback
            if checked:
                self.icon_manager.apply_icon(self.btn_lock, "locked_icon", "disabled")
            else:
                self.icon_manager.apply_icon(self.btn_lock, "unlocked_icon", "accent")
            
            self.lockToggled.emit(self.dept_id, checked)