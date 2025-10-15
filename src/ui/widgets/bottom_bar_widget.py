from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget


class BottomBarWidget(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._go_to_list_callback = None
        self._inbox_callback = None
        self.setup_ui()

        self.controller.signals.emails_changed.connect(self.update_inbox_button)

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.inbox_btn = QPushButton("✉ Inbox")
        self.inbox_btn.clicked.connect(self._on_inbox_clicked)
        layout.addWidget(self.inbox_btn)

        go_to_list_btn = QPushButton("Go-To List")
        go_to_list_btn.clicked.connect(self._on_go_to_list_clicked)
        layout.addWidget(go_to_list_btn)

    def set_go_to_list_callback(self, callback):
        self._go_to_list_callback = callback

    def set_inbox_callback(self, callback):
        self._inbox_callback = callback

    def _on_go_to_list_clicked(self):
        if self._go_to_list_callback:
            self._go_to_list_callback()

    def _on_inbox_clicked(self):
        if self._inbox_callback:
            self._inbox_callback()

    def update_inbox_button(self):
        unread_count = self.controller.get_unread_email_count()
        if unread_count > 0:
            self.inbox_btn.setText(f"Inbox ({unread_count})")
            self.inbox_btn.setStyleSheet("background-color: #3d9046;")
        else:
            self.inbox_btn.setText("Inbox")
            self.inbox_btn.setStyleSheet("")

    def update_initial_state(self):
        self.update_inbox_button()
