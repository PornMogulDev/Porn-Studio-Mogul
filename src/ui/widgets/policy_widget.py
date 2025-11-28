from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QCheckBox, QLabel
)
from PyQt6.QtCore import Qt

class PolicyWidget(QFrame):
    """
    Widget representing a single policy row with a checkbox, description, and cost.
    Uses object names and properties to allow styling via ThemeManager.
    """
    def __init__(self, policy_def: dict, is_active: bool, parent=None):
        super().__init__(parent)
        self.policy_id = policy_def.get('id')
        
        # Setup container styling
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("policyItem")
        
        self._setup_ui(policy_def, is_active)

    def _setup_ui(self, policy_def, is_active):
        layout = QHBoxLayout(self)
        
        # --- Left side: Checkbox (Title) + Description ---
        text_layout = QVBoxLayout()
        
        self.checkbox = QCheckBox(policy_def.get('name', 'Unknown Policy'))
        self.checkbox.setChecked(is_active)
        self.checkbox.setObjectName("policyCheckbox")
        
        description = QLabel(policy_def.get('description', ''))
        description.setWordWrap(True)
        description.setObjectName("policyDescription")
        
        text_layout.addWidget(self.checkbox)
        text_layout.addWidget(description)
        
        layout.addLayout(text_layout, stretch=1)
        
        # --- Right side: Costs ---
        cost_layout = QVBoxLayout()
        cost_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        
        # Parse costs
        per_scene = policy_def.get('per_scene_cost', 0)
        weekly = policy_def.get('weekly_upkeep', 0)
        
        # Create labels with 'cost_type' property for CSS styling
        if per_scene > 0:
            lbl = QLabel(f"${per_scene} / scene")
            lbl.setObjectName("policyCostLabel")
            lbl.setProperty("cost_type", "per_scene")
            cost_layout.addWidget(lbl)
            
        if weekly > 0:
            lbl = QLabel(f"${weekly} / week")
            lbl.setObjectName("policyCostLabel")
            lbl.setProperty("cost_type", "weekly")
            cost_layout.addWidget(lbl)
            
        if per_scene == 0 and weekly == 0:
            lbl = QLabel("No Cost")
            lbl.setObjectName("policyCostLabel")
            lbl.setProperty("cost_type", "free")
            cost_layout.addWidget(lbl)
            
        layout.addLayout(cost_layout)