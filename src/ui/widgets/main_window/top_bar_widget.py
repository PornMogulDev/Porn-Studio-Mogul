from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtWidgets import ( QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QSpacerItem, QWidget, QToolButton
)

from ui.widgets.help_button import HelpButton
from ui.managers.icon_manager import IconManager

class TopBarWidget(QWidget):
    # Signals to replace direct controller calls
    menu_clicked = pyqtSignal()
    next_week_clicked = pyqtSignal()
    help_requested = pyqtSignal(str)
    inbox_clicked = pyqtSignal()

    def __init__(self, icon_manager: IconManager, parent=None):
        super().__init__(parent)
        self.icon_manager = icon_manager
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)

        menu_btn = QPushButton("☰ Menu")
        menu_btn.setToolTip("Open Game Menu (Esc)")
        menu_btn.clicked.connect(self.menu_clicked.emit)
        layout.addWidget(menu_btn)

        # --- Inbox Button (Replaces Bottom Bar Inbox) ---
        self.inbox_btn = QToolButton()
        self.inbox_btn.setText("Inbox")
        self.inbox_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        # Assuming 'inbox.svg' exists in assets/icons
        self.inbox_btn.setIcon(self.icon_manager.get_icon("read_icon")) 
        self.inbox_btn.setIconSize(QSize(20, 20))
        self.inbox_btn.clicked.connect(self.inbox_clicked.emit)
        self.inbox_btn.setStyleSheet("QToolButton { border: none; font-weight: bold; } QToolButton:hover { color: #0078D7; }")
        layout.addWidget(self.inbox_btn)

        next_week_btn = QPushButton("Next Week ►")
        next_week_btn.setToolTip("Advance to the next week")
        next_week_btn.clicked.connect(self.next_week_clicked.emit)
        layout.addWidget(next_week_btn)

        layout.addStretch()
        
        # HelpButton internally emits help_requested, we pass it up
        help_btn = HelpButton("overview", self)
        help_btn.help_requested.connect(self.help_requested.emit)
        layout.addWidget(help_btn)

        layout.addSpacerItem(
            QSpacerItem(
                40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
            )
        )

        self.money_label = QLabel("Money: $---")
        self.money_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.money_label)

        self.time_label = QLabel("Week: --, Year: ----")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.time_label)

    def update_inbox_count(self, unread_count: int):
        """Updates icon and text based on unread count."""
        if unread_count > 0:
            self.inbox_btn.setText(f"Inbox ({unread_count})")
            # Use 'inbox_unread' icon or a colored version of standard inbox
            # Assuming 'inbox_unread.svg' exists, or we color the standard one red
            self.inbox_btn.setIcon(self.icon_manager.get_icon("unread_icon"))
        else:
            self.inbox_btn.setText("Inbox")
            self.inbox_btn.setIcon(self.icon_manager.get_icon("read_icon"))

    def update_money_display(self, money: int):
        self.money_label.setText(f"Money: ${money:,}")

    def update_time_display(self, week: int, year: int):
        self.time_label.setText(f"Week {week}, Year {year}")