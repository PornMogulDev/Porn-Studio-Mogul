import logging
from typing import List

from core.interfaces import GameSignals
from data.game_state import GameState, EmailMessage
from database.db_models import EmailMessageDB

logger = logging.getLogger(__name__)

class EmailService:
    """Manages all database operations related to emails."""

    def __init__(self, db_session, signals: GameSignals, game_state: GameState):
        self.session = db_session
        self.signals = signals
        self.game_state = game_state

    def get_all_emails(self) -> List[EmailMessage]:
        """Fetches all emails, sorted by most recent."""
        emails_db = self.session.query(EmailMessageDB).order_by(
            EmailMessageDB.year.desc(), 
            EmailMessageDB.week.desc(), 
            EmailMessageDB.id.desc()
        ).all()
        return [e.to_dataclass(EmailMessage) for e in emails_db]

    def get_unread_email_count(self) -> int:
        """Returns the count of unread emails."""
        return self.session.query(EmailMessageDB).filter_by(is_read=False).count()

    def create_email(self, subject: str, body: str) -> bool:
        """Creates and saves a new email for the current game week."""
        try:
            new_email = EmailMessageDB(
                subject=subject, 
                body=body, 
                week=self.game_state.week, 
                year=self.game_state.year, 
                is_read=False
            )
            self.session.add(new_email)
            self.session.commit()
            self.signals.emails_changed.emit()
            return True
        except Exception as e:
            logger.error(f"Failed to create email: {e}")
            self.session.rollback()
            return False

    def mark_email_as_read(self, email_id: int):
        """Marks a single email as read."""
        try:
            email_db = self.session.query(EmailMessageDB).get(email_id)
            if email_db and not email_db.is_read:
                email_db.is_read = True
                self.session.commit()
                self.signals.emails_changed.emit()
        except Exception as e:
            logger.error(f"Failed to mark email {email_id} as read: {e}")
            self.session.rollback()

    def delete_emails(self, email_ids: list[int]):
        """Deletes a list of emails by their IDs."""
        if not email_ids:
            return
        try:
            self.session.query(EmailMessageDB).filter(
                EmailMessageDB.id.in_(email_ids)
            ).delete(synchronize_session=False)
            self.session.commit()
            self.signals.emails_changed.emit()
        except Exception as e:
            logger.error(f"Failed to delete emails: {e}")
            self.session.rollback()