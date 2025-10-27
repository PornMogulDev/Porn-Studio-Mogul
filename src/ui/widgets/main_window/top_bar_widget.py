from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import ( QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QSpacerItem, QWidget,
)

from ui.widgets.help_button import HelpButton

class TopBarWidget(QWidget):
    help_requested = pyqtSignal(str)
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._menu_callback = None
        self.setup_ui()

        self.controller.signals.money_changed.connect(self.update_money_display)
        self.controller.signals.time_changed.connect(self.update_time_display)

    def setup_ui(self):
        layout = QHBoxLayout(self)

        menu_btn = QPushButton("☰ Menu")
        menu_btn.setToolTip("Open Game Menu (Esc)")
        menu_btn.clicked.connect(self._on_menu_clicked)
        layout.addWidget(menu_btn)

        next_week_btn = QPushButton("Next Week ►")
        next_week_btn.setToolTip("Advance to the next week")
        next_week_btn.clicked.connect(self.controller.advance_week)
        layout.addWidget(next_week_btn)

        layout.addStretch()
        help_btn = HelpButton("overview", self)
        help_btn.help_requested.connect(self.help_requested)
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

    def set_menu_callback(self, callback):
        self._menu_callback = callback

    def _on_menu_clicked(self):
        if self._menu_callback:
            self._menu_callback()

    def update_money_display(self, money: int):
        self.money_label.setText(f"Money: ${money:,}")

    def update_time_display(self, week: int, year: int):
        self.time_label.setText(f"Week {week}, {year}")

    def update_initial_state(self):
        self.update_money_display(self.controller.game_state.money)
        self.update_time_display(
            self.controller.game_state.week, self.controller.game_state.year
        )
