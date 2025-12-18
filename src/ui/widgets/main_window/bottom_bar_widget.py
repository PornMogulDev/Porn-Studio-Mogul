from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget
from PyQt6.QtCore import pyqtSignal

class BottomBarWidget(QWidget):
    inbox_clicked = pyqtSignal()
    go_to_list_clicked = pyqtSignal()
    policies_clicked = pyqtSignal()
    roster_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        go_to_list_btn = QPushButton("Go-To List")
        go_to_list_btn.clicked.connect(self.go_to_list_clicked.emit)
        layout.addWidget(go_to_list_btn)

        roster_btn = QPushButton("Roster")
        roster_btn.clicked.connect(self.roster_clicked.emit)
        layout.addWidget(roster_btn)

        policies_btn = QPushButton("Studio Policies")
        policies_btn.clicked.connect(self.policies_clicked.emit)
        layout.addWidget(policies_btn)