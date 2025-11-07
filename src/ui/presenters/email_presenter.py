from typing import List, Optional, TYPE_CHECKING
from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QMessageBox

from core.interfaces import IGameController
from ui.view_models import EmailListItemViewModel, EmailContentViewModel

if TYPE_CHECKING:
    from ui.dialogs.email_dialog import EmailDialog

class EmailPresenter(QObject):
    """
    Presenter for the EmailDialog. Handles all logic for fetching emails,
    managing selection state, and processing user actions like marking as read
    and deleting.
    """
    def __init__(self, controller: IGameController, view: 'EmailDialog', parent=None):
        super().__init__(parent)
        self.controller = controller
        self.view = view

        # --- Internal State ---
        self.current_selected_id: Optional[int] = None

        # --- Signal Connections ---
        self.controller.signals.emails_changed.connect(self.load_initial_data)
        
        self.view.email_selected.connect(self.on_email_selected)
        self.view.delete_requested.connect(self.on_delete_requested)
        self.view.help_requested.connect(self.on_help_requested)

    @pyqtSlot()
    def load_initial_data(self):
        """
        The main entry point for refreshing the dialog. Fetches all emails,
        formats them into view models, and commands the view to update.
        """
        all_emails = self.controller.get_all_emails()

        # Build the view model for the list
        list_vms = [
            EmailListItemViewModel(
                id=email.id,
                subject=email.subject,
                is_bold=not email.is_read
            ) for email in all_emails
        ]

        self.view.update_email_list(list_vms, self.current_selected_id)
        
        # After updating the list, ensure the details pane is also correct.
        # This handles cases where the selected email might have been deleted.
        if self.current_selected_id and not any(vm.id == self.current_selected_id for vm in list_vms):
            self.current_selected_id = None
        
        self.on_email_selected(self.current_selected_id)


    @pyqtSlot(object)
    def on_email_selected(self, email_id: Optional[int]):
        """
        Handles the selection of an email from the list. Fetches its content,
        marks it as read if necessary, and updates the details pane.
        """
        self.current_selected_id = email_id

        if email_id is None:
            # No email is selected, so command the view to show an empty state.
            empty_vm = EmailContentViewModel(is_visible=False)
            self.view.display_email_content(empty_vm)
            return

        # Fetch the full email object to get its details
        # Note: We refetch here to ensure we have the most current data.
        email_obj = next((e for e in self.controller.get_all_emails() if e.id == email_id), None)

        if email_obj:
            # Build the view model for the content pane
            content_vm = EmailContentViewModel(
                subject=f"Subject: {email_obj.subject}",
                date_str=f"Date: Week {email_obj.week}, {email_obj.year}",
                body=email_obj.body
            )
            self.view.display_email_content(content_vm)

            # If the email was unread, trigger the logic to mark it as read.
            # The controller will then emit emails_changed, which will cause
            # load_initial_data to run and update the list's bolding.
            if not email_obj.is_read:
                self.controller.mark_email_as_read(email_obj.id)
        else:
            # This can happen if the email was deleted by another process
            # between the list being populated and the user clicking.
            self.current_selected_id = None
            empty_vm = EmailContentViewModel(is_visible=False)
            self.view.display_email_content(empty_vm)


    @pyqtSlot(list)
    def on_delete_requested(self, email_ids: List[int]):
        """
        Handles the request to delete one or more emails, showing a confirmation
        dialog first.
        """
        if not email_ids:
            return

        reply = QMessageBox.question(self.view, "Confirm Delete",
                                     f"Are you sure you want to delete {len(email_ids)} message(s)?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self.controller.delete_emails(email_ids)

    @pyqtSlot(str)
    def on_help_requested(self, topic_key: str):
        """Forwards a help request to the global help handler."""
        self.controller.signals.show_help_requested.emit(topic_key)