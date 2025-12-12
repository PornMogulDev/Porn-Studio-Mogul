from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import ( QHBoxLayout, QLabel, QSizePolicy,
    QSpacerItem, QWidget, QToolButton
)

from ui.widgets.buttons.help_button import HelpButton
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

        self.last_unread_count = 0

        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)

        self.menu_btn = QToolButton()
        self.menu_btn.setToolTip("Open Game Menu (Esc)")
        self.icon_manager.apply_icon(self.menu_btn, "game_menu_icon", "accent")
        self.menu_btn.clicked.connect(self.menu_clicked.emit)
        layout.addWidget(self.menu_btn)

        # --- Inbox Button ---
        self.inbox_btn = QToolButton()
        self.inbox_btn.setToolTip("Inbox")
        # Initial State: "text" (default)
        self.icon_manager.apply_icon(self.inbox_btn, "read_icon", "accent")
        self.inbox_btn.clicked.connect(self.inbox_clicked.emit)
        layout.addWidget(self.inbox_btn)

        self.next_week_btn = QToolButton()
        self.next_week_btn.setToolTip("Advance to the next week (P)")
        self.icon_manager.apply_icon(self.next_week_btn, "next_icon", "accent")
        self.next_week_btn.clicked.connect(self.next_week_clicked.emit)
        layout.addWidget(self.next_week_btn)

        layout.addStretch()
        
        # HelpButton internally emits help_requested, we pass it up
        self.help_btn = HelpButton("overview", self.icon_manager, self)
        self.help_btn.help_requested.connect(self.help_requested.emit)
        layout.addWidget(self.help_btn)

        layout.addSpacerItem(
            QSpacerItem(
                40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
            )
        )

        self.money_label = QLabel("Money: $---")
        self.money_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.money_label)

        self.time_label = QLabel("Month: --, Week: --, Year: ----")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.time_label)

    def update_inbox_count(self, unread_count: int):
        """Updates icon and text based on unread count."""
        self.last_unread_count = unread_count
        if unread_count > 0:
            self.inbox_btn.setToolTip(f"Inbox, {unread_count} unread messages")
            # Set Property: Warning
            self.icon_manager.apply_icon(self.inbox_btn, "unread_icon", "warning")
        else:
            # Set Property: Text (Normal)
            self.inbox_btn.setToolTip("Inbox")
            self.icon_manager.apply_icon(self.inbox_btn, "read_icon", "accent")
    
    def refresh_icons(self):
        """Refreshes icons to apply new scaling or themes."""
        self.icon_manager.apply_icon(self.menu_btn, "game_menu_icon", "accent")
        self.icon_manager.apply_icon(self.next_week_btn, "next_icon", "accent")

        if hasattr(self.help_btn, "refresh_icon"):
            self.help_btn.refresh_icon()
        
        # Use the stored count to refresh the inbox state correctly
        if hasattr(self, 'last_unread_count'):
            self.update_inbox_count(self.last_unread_count)

    def update_money_display(self, money: int):
        self.money_label.setText(f"Money: ${money:,}")

    def update_time_display(self, month: int, week: int, year: int):
        self.time_label.setText(f"Month {month}, Week {week}, Year {year}")