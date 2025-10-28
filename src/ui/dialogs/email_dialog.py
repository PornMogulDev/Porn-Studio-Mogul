from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QTextEdit, QLabel, QPushButton, QDialogButtonBox, QMessageBox,
)
from PyQt6.QtCore import Qt, QSize

from ui.mixins.geometry_manager_mixin import GeometryManagerMixin
from ui.widgets.help_button import HelpButton
from ui.widgets.revert_geometry_button import RestoreGeometryButton

class EmailDialog(GeometryManagerMixin, QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.settings_manager = self.controller.settings_manager
        theme_name = self.settings_manager.get_setting("theme", "dark")
        self.current_theme = self.controller.theme_manager.get_theme(theme_name)
        self.setWindowTitle("Inbox")
        self.defaultSize = QSize(600, 500)

        self.setup_ui()
        self.connect_signals()
        
        self.refresh_ui()

        self._restore_geometry()

        # After the UI is built and populated, we can set the initial state.
        # First, check if there are any items to prevent an error.
        if self.email_list_widget.count() > 0:
            # Programmatically select the first item in the list (index 0).
            self.email_list_widget.setCurrentRow(0)
            # Explicitly give the list widget keyboard focus.
            self.email_list_widget.setFocus()

    def setup_ui(self):
        main_layout = QHBoxLayout(self)

        # --- Left Panel (Email List) ---
        left_panel = QVBoxLayout()
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Messages"), 3)
        top_layout.addStretch(3)
        revert_btn = RestoreGeometryButton(parent=self)
        top_layout.addWidget(revert_btn, 1)
        self.help_btn = HelpButton("email", self)
        top_layout.addWidget(self.help_btn, 1)
        left_panel.addLayout(top_layout)

        self.email_list_widget = QListWidget()
        self.email_list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        left_panel.addWidget(self.email_list_widget)
        
        button_layout = QHBoxLayout()
        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.setEnabled(False)
        button_layout.addWidget(self.delete_btn)
        button_layout.addStretch()
        left_panel.addLayout(button_layout)
        
        # --- Right Panel (Email Content) ---
        right_panel = QVBoxLayout()
        self.subject_label = QLabel("Subject: (Select a message)")
        self.subject_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        
        self.date_label = QLabel("Date:")
        self.date_label.setStyleSheet(f"color: {self.current_theme.color_neutral};")
        
        self.body_text = QTextEdit()
        self.body_text.setReadOnly(True)
        
        right_panel.addWidget(self.subject_label)
        right_panel.addWidget(self.date_label)
        right_panel.addWidget(self.body_text)
        
        close_button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        right_panel.addWidget(close_button_box)

        main_layout.addLayout(left_panel, 1)
        main_layout.addLayout(right_panel, 2)
        
        close_button_box.rejected.connect(self.reject)

    def connect_signals(self):
        self.email_list_widget.currentItemChanged.connect(self.on_email_selected)
        self.email_list_widget.selectionModel().selectionChanged.connect(self.update_button_state)
        self.controller.signals.emails_changed.connect(self.refresh_ui)
        self.delete_btn.clicked.connect(self.delete_selected_emails)
        self.help_btn.help_requested.connect(self.controller.signals.show_help_requested)

    def refresh_ui(self):
        """Repopulates the list and maintains selection if possible."""
        current_email_obj = None
        if current_item := self.email_list_widget.currentItem():
            current_email_obj = current_item.data(Qt.ItemDataRole.UserRole)

        self.email_list_widget.clear()
        
        # Fetch emails directly from the controller's DB query method
        all_emails = self.controller.get_all_emails()

        item_to_reselect = None
        for email in all_emails:
            item = QListWidgetItem(email.subject)
            # Store the entire object for easy access later
            item.setData(Qt.ItemDataRole.UserRole, email) 
            
            if not email.is_read:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            
            self.email_list_widget.addItem(item)
            if current_email_obj and email.id == current_email_obj.id:
                item_to_reselect = item

        if item_to_reselect:
            self.email_list_widget.setCurrentItem(item_to_reselect)
        else:
            self.clear_details()
            self.update_button_state()

    def on_email_selected(self, current_item, previous_item):
        if not current_item:
            self.clear_details()
            return
            
        # Get the full email object directly from the item data
        email_obj = current_item.data(Qt.ItemDataRole.UserRole)
        
        if email_obj:
            self.subject_label.setText(f"Subject: {email_obj.subject}")
            self.date_label.setText(f"Date: Week {email_obj.week}, {email_obj.year}")
            self.body_text.setPlainText(email_obj.body)
            
            # If it was unread, mark it as read
            if not email_obj.is_read:
                self.controller.mark_email_as_read(email_obj.id)
                # The connected signal will trigger refresh_ui to update the font.

    def update_button_state(self):
        self.delete_btn.setEnabled(len(self.email_list_widget.selectedItems()) > 0)

    def delete_selected_emails(self):
        selected_items = self.email_list_widget.selectedItems()
        if not selected_items:
            return
            
        reply = QMessageBox.question(self, "Confirm Delete", 
                                     f"Are you sure you want to delete {len(selected_items)} message(s)?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            ids_to_delete = [item.data(Qt.ItemDataRole.UserRole).id for item in selected_items]
            self.controller.delete_emails(ids_to_delete)

    def clear_details(self):
        self.subject_label.setText("Subject: (Select a message)")
        self.date_label.setText("Date:")
        self.body_text.clear()