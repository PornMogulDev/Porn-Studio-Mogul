from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget
from PyQt6.QtCore import pyqtSignal

class BottomBarWidget(QWidget):
    inbox_clicked = pyqtSignal()
    go_to_list_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.inbox_btn = QPushButton("✉ Inbox")
        self.inbox_btn.setObjectName("inboxBtn") # Crucial for QSS targeting
        self.inbox_btn.clicked.connect(self.inbox_clicked.emit)
        layout.addWidget(self.inbox_btn)

        go_to_list_btn = QPushButton("Go-To List")
        go_to_list_btn.clicked.connect(self.go_to_list_clicked.emit)
        layout.addWidget(go_to_list_btn)

    def update_inbox_count(self, unread_count: int):
        """
        Updates the inbox button text and toggles the semantic property.
        """
        # 1. Update Text
        if unread_count > 0:
            self.inbox_btn.setText(f"Inbox ({unread_count})")
        else:
            self.inbox_btn.setText("Inbox")

        # 2. Update State Property
        has_unread = unread_count > 0
        
        # Only trigger a style refresh if the state actually changed to avoid flickering
        if self.inbox_btn.property("has_unread") != has_unread:
            self.inbox_btn.setProperty("has_unread", has_unread)
            
            # 3. Force Style Refresh (Qt doesn't auto-refresh style on property change)
            self.inbox_btn.style().unpolish(self.inbox_btn)
            self.inbox_btn.style().polish(self.inbox_btn)