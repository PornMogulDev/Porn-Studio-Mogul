import logging
from typing import List, Dict

from core.game_signals import GameSignals
from data.game_state import GameState, EmailMessage
from database.db_models import EmailMessageDB

logger = logging.getLogger(__name__)

class EmailService:
    """Manages all database operations related to emails."""

    def __init__(self, session_factory, signals: GameSignals, game_state: GameState):
        self.session_factory = session_factory
        self.signals = signals
        self.game_state = game_state

    def _create_email(self, session, subject: str, body: str):
        """Internal helper that adds an email to the session without committing."""
        new_email = EmailMessageDB(
            subject=subject,
            body=body,
            week=self.game_state.week,
            year=self.game_state.year,
            is_read=False
        )
        session.add(new_email)

    def mark_email_as_read(self, email_id: int):
        """Marks a single email as read."""
        session = self.session_factory()
        try:
            email_db = session.query(EmailMessageDB).get(email_id)
            if email_db and not email_db.is_read:
                email_db.is_read = True
                session.commit()
                self.signals.emails_changed.emit()
        except Exception as e:
            logger.error(f"Failed to mark email {email_id} as read: {e}")
            session.rollback()
        finally:
            session.close()

    def delete_emails(self, email_ids: list[int]):
        """Deletes a list of emails by their IDs."""
        if not email_ids:
            return
        session = self.session_factory()
        try:
            session.query(EmailMessageDB).filter(
                EmailMessageDB.id.in_(email_ids)
            ).delete(synchronize_session=False)
            session.commit()
            self.signals.emails_changed.emit()
        except Exception as e:
            logger.error(f"Failed to delete emails: {e}")
            session.rollback()
        finally:
            session.close()

    def create_market_discovery_email(self, session, scene_title: str, discoveries: Dict[str, List[str]]):
        """
        Creates a formatted email for market discoveries within an existing transaction.
        This is an Orchestrated Method. The caller is responsible for the commit.
        """
        if not discoveries:
            return

        subject = f"Market Research Results: '{scene_title}'"
        body = "Our analysis of the release of your recent scene has yielded new market insights.\n\n"
        for group_name, tags in discoveries.items():
            body += f"<p><b>{group_name}:</b></p>"
            tag_list = "".join([f"<li>Discovered preference for '<b>{tag}</b>'</li>" for tag in sorted(tags)])
            body += f"<ul>{tag_list}</ul>"
        body += "<p>This information has been added to our market intelligence reports.</p>"

        self._create_email(session, subject, body)