from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLabel
from PyQt6.QtCore import Qt

class RoleDetailsWidget(QWidget):
    """Widget displaying details about the selected role."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.details_display = QTextEdit()
        self.details_display.setReadOnly(True)
        self.details_display.setMaximumHeight(250)
        layout.addWidget(self.details_display)
        
        self.no_selection_label = QLabel("Select a scene and role to view details")
        self.no_selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_selection_label.setWordWrap(True)
        layout.addWidget(self.no_selection_label)
        
        layout.addStretch()
        
        self._show_no_selection()
    
    def update_role_details(self, html: str):
        """Update the display with role details HTML."""
        self.details_display.setHtml(html)
        self.details_display.show()
        self.no_selection_label.hide()
    
    def _show_no_selection(self):
        """Show placeholder when no role is selected."""
        self.details_display.clear()
        self.details_display.hide()
        self.no_selection_label.show()
    
    def clear(self):
        """Clear the role details."""
        self._show_no_selection()