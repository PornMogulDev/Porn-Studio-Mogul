import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from database.db_models import EmailMessageDB, GameInfoDB
from data.data_manager import DataManager
from core.game_signals import GameSignals
from utils import time_utils

logger = logging.getLogger(__name__)

class EmailService:
    """
    Handles operations related to the email system, including creating new emails
    from templates and managing read/delete states.
    """
    def __init__(self, session_factory, signals: GameSignals, data_manager: DataManager):
        self.session_factory = session_factory
        self.signals = signals
        self.data_manager = data_manager

    def mark_email_as_read(self, email_id: int):
        with self.session_factory() as session:
            email = session.query(EmailMessageDB).get(email_id)
            if email:
                email.is_read = True
                session.commit()
                self.signals.emails_changed.emit()

    def delete_emails(self, email_ids: List[int]):
         with self.session_factory() as session:
            session.query(EmailMessageDB).filter(EmailMessageDB.id.in_(email_ids)).delete(synchronize_session=False)
            session.commit()
            self.signals.emails_changed.emit()

    def create_email_from_template(self, session: Session, template_key: str, variables: Dict[str, Any] = None):
        """
        Creates an email record in the current session using a JSON template.
        Does NOT commit the session (allows caller to bundle with other changes).
        """
        if variables is None:
            variables = {}

        template = self.data_manager.emails.get(template_key)
        if not template:
            logger.error(f"Email template '{template_key}' not found.")
            return

        try:
            subject = template.get('subject', '').format(**variables)
            body = template.get('body', '').format(**variables)
        except KeyError as e:
            logger.error(f"Missing variable for email template '{template_key}': {e}")
            return

        # Determine current week
        abs_week_info = session.query(GameInfoDB).filter_by(key='absolute_week').first()
        current_week = int(abs_week_info.value) if abs_week_info else 1

        new_email = EmailMessageDB(
            subject=subject,
            body=body,
            absolute_week=current_week,
            is_read=False
        )
        session.add(new_email)

    def create_tour_booking_email(self, session: Session, talent_id: int, talent_name: str, 
                                  destination: str, duration: int, start_absolute_week: int, 
                                  sponsor_type: str, ai_studio_name: Optional[str] = None):
        """
        Convenience method to create tour notification emails.
        Formats the absolute week into a readable string (Week X, Year Y).
        """
        year, week = time_utils.from_absolute(start_absolute_week)
        date_str = f"Week {week}, Year {year}"

        variables = {
            'talent_id': talent_id,
            'talent_name': talent_name,
            'destination': destination,
            'duration': duration,
            'start_date': date_str,
            'ai_studio_name': ai_studio_name or "Unknown Studio"
        }

        template_key = ""
        if sponsor_type == 'player':
            template_key = "tour_booked_player_sponsored"
        elif sponsor_type == 'self':
            template_key = "tour_booked_autonomous"
        elif sponsor_type == 'ai_studio':
             template_key = "tour_booked_ai_sponsored"
        
        if template_key:
            self.create_email_from_template(session, template_key, variables)

    def create_market_discovery_email(self, session: Session, scene_title: str, discoveries: Dict[str, List[str]]):
        """
        Creates an email summarizing new market discoveries.
        """
        template = self.data_manager.emails.get('market_discovery')
        if not template:
            logger.error("Email template 'market_discovery' not found.")
            return

        # Start with the header
        body_parts = [template.get('body_header', '<p>New discoveries:</p>')]

        # Iterate through discoveries and build the list
        for group_name, tags in discoveries.items():
            # Add group header
            group_header = template.get('body_group', '<p><b>{group_name}:</b></p>').format(group_name=group_name)
            body_parts.append(group_header)
            
            # Add tags list
            body_parts.append("<ul>")
            for tag in tags:
                item_str = template.get('body_tag_item', '<li>{tag}</li>').format(tag=tag)
                body_parts.append(item_str)
            body_parts.append("</ul>")

        # Add footer
        body_parts.append(template.get('body_footer', ''))

        # Combine into a single body string
        final_body = "".join(body_parts)

        # Create variable dict just for the subject line
        variables = {'scene_title': scene_title}
        subject = template.get('subject', 'Market Research Results').format(**variables)

        # Save to DB
        abs_week_info = session.query(GameInfoDB).filter_by(key='absolute_week').first()
        current_week = int(abs_week_info.value) if abs_week_info else 1

        new_email = EmailMessageDB(
            subject=subject,
            body=final_body,
            absolute_week=current_week,
            is_read=False
        )
        session.add(new_email)