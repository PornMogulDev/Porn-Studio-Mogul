from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, 
    QScrollArea, QWidget
)
from PyQt6.QtCore import Qt, QSize

from ui.mixins.geometry_manager_mixin import GeometryManagerMixin
from ui.widgets.policy_widget import PolicyWidget

class PolicyDialog(QDialog, GeometryManagerMixin):
    """
    Modeless dialog for managing Studio-wide policies.
    """
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.presenter = None
        self.settings_manager = settings_manager
        self.setWindowTitle("Studio Policies")
        self.defaultSize = QSize(700, 700)

        self.setup_ui()
        self._restore_geometry()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header - Styling handled by QSS via ID
        header = QLabel("Active Studio Policies")
        header.setObjectName("policyDialogHeader")
        layout.addWidget(header)
        
        desc = QLabel("Policies apply to all future productions and studio operations.")
        desc.setObjectName("policyDialogSubHeader")
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
            
            # Using the new separated Widget
            item = PolicyWidget(policy_def, is_active)
            
            # Connect signal from the checkbox inside the widget
            item.checkbox.toggled.connect(
                lambda checked, pid=p_id: self.presenter.on_policy_toggled(pid, checked)
            )
            
            self.scroll_layout.addWidget(item)