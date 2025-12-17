import logging
from typing import List, Dict, Any, Optional
from jinja2 import TemplateError
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
        if variables is None:
            variables = {}

        # 1. Look up metadata in emails.json
        meta = self.data_manager.emails.get(template_key)
        if not meta:
            logger.error(f"Email metadata '{template_key}' not found in emails.json.")
            return

        template_file = meta.get('template')
        subject_str = meta.get('subject', 'No Subject')

        try:
            # 2. Render Body via Jinja2
            # The DataManager holds the env configured to the templates directory
            jinja_template = self.data_manager.jinja_env.get_template(template_file)
            body = jinja_template.render(**variables)
            
            # 3. Render Subject (Jinja allows logic in subjects too, e.g. "Alert: {{ name }}")
            # We create a temporary string template for the subject line
            subject_template = self.data_manager.jinja_env.from_string(subject_str)
            subject = subject_template.render(**variables)

        except TemplateError as e:
            logger.error(f"Jinja2 rendering error for '{template_key}': {e}")
            return

        # 4. Save to DB
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
        Refactored to simply pass data to the Jinja template.
        All manual HTML construction has been deleted.
        """
        variables = {
            'scene_title': scene_title,
            'discoveries': discoveries # Pass the dictionary directly!
        }
        
        # 'market_discovery' in emails.json now points to 'market_discovery.html'
        self.create_email_from_template(session, 'market_discovery', variables)