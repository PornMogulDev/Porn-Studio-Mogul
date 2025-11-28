from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QScrollArea, QWidget, QCheckBox, QFrame
)
from PyQt6.QtCore import Qt

class PolicyItemWidget(QFrame):
    """
    Widget representing a single policy row with a checkbox, description, and cost.
    """
    def __init__(self, policy_def, is_active, parent=None):
        super().__init__(parent)
        self.policy_id = policy_def.get('id')
        self.setup_ui(policy_def, is_active)
        
        # Styling
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("policyItem")

    def setup_ui(self, policy_def, is_active):
        layout = QHBoxLayout(self)
        
        # Left side: Checkbox (Title) + Description
        text_layout = QVBoxLayout()
        
        self.checkbox = QCheckBox(policy_def.get('name', 'Unknown Policy'))
        self.checkbox.setChecked(is_active)
        self.checkbox.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        description = QLabel(policy_def.get('description', ''))
        description.setWordWrap(True)
        description.setStyleSheet("color: #888; font-size: 11px;")
        
        text_layout.addWidget(self.checkbox)
        text_layout.addWidget(description)
        
        layout.addLayout(text_layout, stretch=1)
        
        # Right side: Costs
        cost_layout = QVBoxLayout()
        cost_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        
        # Supports old 'per_scene_cost' or generalized cost keys if JSON changes
        per_scene = policy_def.get('per_scene_cost', 0)
        weekly = policy_def.get('weekly_upkeep', 0)
        
        if per_scene > 0:
            lbl = QLabel(f"${per_scene} / scene")
            lbl.setStyleSheet("color: #d9534f;") # Red-ish
            cost_layout.addWidget(lbl)
            
        if weekly > 0:
            lbl = QLabel(f"${weekly} / week")
            lbl.setStyleSheet("color: #f0ad4e;") # Orange-ish
            cost_layout.addWidget(lbl)
            
        if per_scene == 0 and weekly == 0:
            lbl = QLabel("No Cost")
            lbl.setStyleSheet("color: #5cb85c;") # Green
            cost_layout.addWidget(lbl)
            
        layout.addLayout(cost_layout)

class PolicyDialog(QDialog):
    """
    Modeless dialog for managing Studio-wide policies.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.presenter = None
        self.setWindowTitle("Studio Policies")
        self.resize(500, 600)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Active Studio Policies")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(header)
        
        desc = QLabel("Policies apply to all future productions and studio operations.")
        desc.setStyleSheet("margin-bottom: 10px; color: #aaa;")
        layout.addWidget(desc)

        # Scroll Area for Policies
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area)

    def set_presenter(self, presenter):
        self.presenter = presenter

    def display_policies(self, policy_definitions: list, active_policy_ids: list):
        """
        Populates the scroll area with policy items.
        """
        # Clear existing
        while self.scroll_layout.count():
            child = self.scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Populate
        for policy_def in policy_definitions:
            p_id = policy_def.get('id')
            is_active = p_id in active_policy_ids
            
            item = PolicyItemWidget(policy_def, is_active)
            # Connect signal
            item.checkbox.toggled.connect(
                lambda checked, pid=p_id: self.presenter.on_policy_toggled(pid, checked)
            )
            
            self.scroll_layout.addWidget(item)