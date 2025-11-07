from typing import List, Optional
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QTextEdit, QLabel, QPushButton, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer

from ui.mixins.geometry_manager_mixin import GeometryManagerMixin
from ui.widgets.help_button import HelpButton
from ui.widgets.revert_geometry_button import RestoreGeometryButton
from ui.view_models import EmailListItemViewModel, EmailContentViewModel
from ui.presenters.email_presenter import EmailPresenter

class EmailDialog(GeometryManagerMixin, QDialog):
    # --- Signals for the Presenter ---
    email_selected = pyqtSignal(object) # object allows None
    delete_requested = pyqtSignal(list)
    help_requested = pyqtSignal(str)

    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.presenter: Optional[EmailPresenter] = None
        
        self.setWindowTitle("Inbox")
        self.defaultSize = QSize(600, 500)

        self.setup_ui()
        self.connect_signals()
        self._restore_geometry()

    def set_presenter(self, presenter: EmailPresenter):
        """Links this view to its presenter and triggers the initial data load."""
        self.presenter = presenter
        # Trigger the initial data load after the event loop starts, ensuring
        # the view is fully constructed and visible.
        QTimer.singleShot(0, self.presenter.load_initial_data)

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
        # Assign an object name for QSS targeting
        self.subject_label.setObjectName("emailSubjectLabel")

        self.date_label = QLabel("Date:")
        # Assign an object name for QSS targeting
        self.date_label.setObjectName("emailDateLabel")
        
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
        self.email_list_widget.currentItemChanged.connect(self._on_email_selection_changed)
        self.email_list_widget.selectionModel().selectionChanged.connect(self.update_button_state)
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        self.help_btn.help_requested.connect(self.help_requested)

    def update_email_list(self, emails: List[EmailListItemViewModel], selected_id: Optional[int]):
        """
        Clears and repopulates the email list from a list of view models.
        This is a 'dumb' renderer commanded by the presenter.
        """
        self.email_list_widget.blockSignals(True)
        self.email_list_widget.clear()

        item_to_reselect = None
        for vm in emails:
            item = QListWidgetItem(vm.subject)
            item.setData(Qt.ItemDataRole.UserRole, vm.id) 
            
            if vm.is_bold:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            
            self.email_list_widget.addItem(item)
            if selected_id and vm.id == selected_id:
                item_to_reselect = item

        self.email_list_widget.blockSignals(False)

        if item_to_reselect:
            self.email_list_widget.setCurrentItem(item_to_reselect)
        elif self.email_list_widget.count() > 0:
            self.email_list_widget.setCurrentRow(0)
        
        self.update_button_state()
        self.email_list_widget.setFocus()

    def display_email_content(self, vm: EmailContentViewModel):
        """Updates the details pane with data from a view model."""
        self.subject_label.setText(vm.subject)
        self.date_label.setText(vm.date_str)
        self.body_text.setPlainText(vm.body)

    def update_button_state(self):
        """Updates the enabled state of buttons based on UI state."""
        self.delete_btn.setEnabled(len(self.email_list_widget.selectedItems()) > 0)

    def _on_email_selection_changed(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        """
        Internal slot to capture a selection change and emit a signal with the
        email's ID to the presenter.
        """
        email_id = None
        if current_item:
            email_id = current_item.data(Qt.ItemDataRole.UserRole)
        self.email_selected.emit(email_id)

    def _on_delete_clicked(self):
        """
        Internal slot to gather selected email IDs and emit a signal to the presenter.
        """
        selected_items = self.email_list_widget.selectedItems()
        if not selected_items:
            return
        
        ids_to_delete = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]
        self.delete_requested.emit(ids_to_delete)