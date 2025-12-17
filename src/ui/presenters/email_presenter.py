from typing import List, Optional, TYPE_CHECKING
from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QMessageBox

from core.interfaces import IGameController
from ui.view_models import EmailListItemViewModel, EmailContentViewModel
from utils import time_utils
import logging

if TYPE_CHECKING:
    from ui.dialogs.email_dialog import EmailDialog

logger = logging.getLogger(__name__)

# Class-level counter to track instances
_instance_counter = 0

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

        global _instance_counter
        _instance_counter += 1
        self._instance_id = _instance_counter

        logger.info(f"[EmailPresenter #{self._instance_id}] Created.")

        # --- Internal State ---
        self.current_selected_id: Optional[int] = None
        self._email_cache: dict[int, object] = {}

        # --- Signal Connections ---
        self.controller.signals.emails_changed.connect(self.load_initial_data)

        self.view.email_selected.connect(self.on_email_selected)
        self.view.delete_requested.connect(self.on_delete_requested)
        self.view.help_requested.connect(self.on_help_requested)

        # Connect the cleanup method to the view's destruction
        self.view.destroyed.connect(self.cleanup)


    def cleanup(self):
        logger.info(f"[EmailPresenter #{self._instance_id}] cleanup() called.")
        try:
            self.controller.signals.emails_changed.disconnect(self.load_initial_data)
            self._email_cache.clear()
            logger.info(f"[EmailPresenter #{self._instance_id}] Successfully disconnected from emails_changed")
        except (RuntimeError, TypeError) as e:
            logger.warning(f"[EmailPresenter #{self._instance_id}] Failed to disconnect from emails_changed: {e}")

    @pyqtSlot()
    def load_initial_data(self):
        """
        The main entry point for refreshing the dialog. Fetches all emails,
        formats them into view models, and commands the view to update.
        """
        if not self.view or not self.view.isVisible():
            logger.info(f"[EmailPresenter #{self._instance_id}] Skipping load_initial_data - view is not visible.")
            return
            
        logger.info(f"[EmailPresenter #{self._instance_id}] load_initial_data() called.")
        all_emails = self.controller.get_all_emails()
        # Cache the full objects for O(1) lookup in on_email_selected
        self._email_cache = {e.id: e for e in all_emails}

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
        logger.info(f"[EmailPresenter #{self._instance_id}] on_email_selected({email_id})")
        self.current_selected_id = email_id

        if email_id is None:
            # No email is selected, so command the view to show an empty state.
            logger.info(f"[EmailPresenter #{self._instance_id}] No email selected, showing empty state")
            empty_vm = EmailContentViewModel(is_visible=False)
            self.view.display_email_content(empty_vm)
            return

        # Fetch the full email object to get its details
        email_obj = self._email_cache.get(email_id)
        logger.info(f"[EmailPresenter #{self._instance_id}] Found email: {email_obj.id if email_obj else 'None'}, is_read: {email_obj.is_read if email_obj else 'N/A'}")


        if email_obj:
            year, week = time_utils.from_absolute(email_obj.absolute_week)
            # Build the view model for the content pane
            content_vm = EmailContentViewModel(
                subject=f"Subject: {email_obj.subject}",
                date_str=f"Date: Week {week}, {year}",
                body=email_obj.body
            )
            self.view.display_email_content(content_vm)

            # If the email was unread, trigger the logic to mark it as read.
            # The controller will then emit emails_changed, which will cause
            # load_initial_data to run and update the list's bolding.
            if not email_obj.is_read:
                logger.info(f"[EmailPresenter #{self._instance_id}] Marking email {email_obj.id} as read")
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