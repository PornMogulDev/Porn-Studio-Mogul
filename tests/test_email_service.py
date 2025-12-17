import unittest
from unittest.mock import MagicMock, patch
from jinja2 import TemplateError
from sqlalchemy.orm import Session
from datetime import datetime

from services.command.email_service import EmailService
from database.db_models import EmailMessageDB, GameInfoDB
from data.data_manager import DataManager
from core.game_signals import GameSignals
from utils import time_utils

class TestEmailCreation(unittest.TestCase):

    def setUp(self):
        self.session_factory = MagicMock()
        self.signals = MagicMock(spec=GameSignals)
        self.data_manager = MagicMock(spec=DataManager)

        # Mock Jinja2 environment and templates
        self.mock_jinja_env = MagicMock()
        self.data_manager.jinja_env = self.mock_jinja_env
        
        self.mock_template = MagicMock()
        self.mock_jinja_env.get_template.return_value = self.mock_template
        self.mock_jinja_env.from_string.return_value = self.mock_template # For subject rendering

        self.service = EmailService(self.session_factory, self.signals, self.data_manager)

        # Common mock for session and query results
        self.mock_session = MagicMock(spec=Session)
        self.session_factory.return_value.__enter__.return_value = self.mock_session
        self.mock_session.query.return_value.filter_by.return_value.first.return_value = \
            MagicMock(spec=GameInfoDB, value='10') # Mock current absolute_week

        # Mock logger to suppress output and check calls
        self.mock_logger_error = MagicMock()
        self.mock_logger_info = MagicMock()
        patch('services.command.email_service.logger.error', self.mock_logger_error).start()
        patch('services.command.email_service.logger.info', self.mock_logger_info).start()
        self.addCleanup(patch.stopall)

    def test_create_email_from_template_success(self):
        # Arrange
        template_key = "welcome_email"
        variables = {"player_name": "TestPlayer"}
        mock_subject = "Welcome, TestPlayer!"
        mock_body = "<p>Hello TestPlayer,</p>"

        self.data_manager.emails = {
            template_key: {"subject": "Welcome, {{ player_name }}!", "template": "welcome.html"}
        }
        self.mock_template.render.side_effect = [mock_body, mock_subject] # First body, then subject

        # Act
        self.service.create_email_from_template(self.mock_session, template_key, variables)

        # Assert
        self.data_manager.jinja_env.get_template.assert_called_once_with("welcome.html")
        self.data_manager.jinja_env.from_string.assert_called_once_with("Welcome, {{ player_name }}!")
        self.assertEqual(self.mock_template.render.call_count, 2) # Body and subject
        self.mock_template.render.assert_any_call(**variables)

        # Verify EmailMessageDB creation and addition
        self.mock_session.add.assert_called_once()
        new_email = self.mock_session.add.call_args[0][0]
        self.assertIsInstance(new_email, EmailMessageDB)
        self.assertEqual(new_email.subject, mock_subject)
        self.assertEqual(new_email.body, mock_body)
        self.assertEqual(new_email.absolute_week, 10)
        self.assertFalse(new_email.is_read)

    def test_create_email_from_template_missing_metadata(self):
        # Arrange
        template_key = "non_existent_email"
        self.data_manager.emails = {} # No metadata for this key

        # Act
        self.service.create_email_from_template(self.mock_session, template_key, {})

        # Assert
        self.mock_logger_error.assert_called_once_with(f"Email metadata '{template_key}' not found in emails.json.")
        self.mock_session.add.assert_not_called()
        self.mock_session.commit.assert_not_called()

    def test_create_email_from_template_jinja_error(self):
        # Arrange
        template_key = "error_email"
        variables = {"missing_key": "will_fail"}
        self.data_manager.emails = {
            template_key: {"subject": "Subject", "template": "error.html"}
        }
        self.mock_template.render.side_effect = TemplateError("Mock Jinja Error")

        # Act
        self.service.create_email_from_template(self.mock_session, template_key, variables)

        # Assert
        self.mock_logger_error.assert_called_once_with(f"Jinja2 rendering error for '{template_key}': Mock Jinja Error")
        self.mock_session.add.assert_not_called()
        self.mock_session.commit.assert_not_called()

    @patch('services.command.email_service.EmailService.create_email_from_template')
    @patch('utils.time_utils.from_absolute', return_value=(2025, 10))
    def test_create_tour_booking_email(self, mock_from_absolute, mock_create_email_from_template):
        # Arrange
        talent_id = 1
        talent_name = "Lexi Starr"
        destination = "Los Angeles"
        duration = 4
        start_absolute_week = 10
        sponsor_type = "player"
        ai_studio_name = None

        expected_variables = {
            'talent_id': talent_id,
            'talent_name': talent_name,
            'destination': destination,
            'duration': duration,
            'start_date': "Week 10, Year 2025",
            'ai_studio_name': "Unknown Studio"
        }

        # Act
        self.service.create_tour_booking_email(
            self.mock_session, talent_id, talent_name,
            destination, duration, start_absolute_week,
            sponsor_type, ai_studio_name
        )

        # Assert
        mock_from_absolute.assert_called_once_with(start_absolute_week)
        mock_create_email_from_template.assert_called_once_with(
            self.mock_session, "tour_booked_player_sponsored", expected_variables
        )

    @patch('services.command.email_service.EmailService.create_email_from_template')
    def test_create_market_discovery_email(self, mock_create_email_from_template):
        # Arrange
        scene_title = "My Great Scene"
        discoveries = {"new_market": ["tag1", "tag2"], "existing_market": ["tag3"]}

        expected_variables = {
            'scene_title': scene_title,
            'discoveries': discoveries
        }

        # Act
        self.service.create_market_discovery_email(self.mock_session, scene_title, discoveries)

        # Assert
        mock_create_email_from_template.assert_called_once_with(
            self.mock_session, "market_discovery", expected_variables
        )

class TestEmailManagement(unittest.TestCase):

    def setUp(self):
        self.session_factory = MagicMock()
        self.signals = MagicMock(spec=GameSignals)
        self.data_manager = MagicMock(spec=DataManager) # Not strictly needed for management, but service requires it
        self.service = EmailService(self.session_factory, self.signals, self.data_manager)

        self.mock_session = MagicMock(spec=Session)
        self.session_factory.return_value.__enter__.return_value = self.mock_session

        # Mock logger
        self.mock_logger_error = MagicMock()
        patch('services.command.email_service.logger.error', self.mock_logger_error).start()
        self.addCleanup(patch.stopall)

    def test_mark_email_as_read_success(self):
        # Arrange
        email_id = 1
        mock_email = MagicMock(spec=EmailMessageDB, id=email_id, is_read=False)
        self.mock_session.query.return_value.get.return_value = mock_email

        # Act
        self.service.mark_email_as_read(email_id)

        # Assert
        self.mock_session.query.assert_called_once_with(EmailMessageDB)
        self.mock_session.query.return_value.get.assert_called_once_with(email_id)
        self.assertTrue(mock_email.is_read)
        self.mock_session.commit.assert_called_once()
        self.signals.emails_changed.emit.assert_called_once()

    def test_mark_email_as_read_not_found(self):
        # Arrange
        email_id = 99
        self.mock_session.query.return_value.get.return_value = None

        # Act
        self.service.mark_email_as_read(email_id)

        # Assert
        self.mock_session.query.assert_called_once_with(EmailMessageDB)
        self.mock_session.query.return_value.get.assert_called_once_with(email_id)
        self.mock_session.commit.assert_not_called()
        self.signals.emails_changed.emit.assert_not_called()

    def test_delete_emails_success(self):
        # Arrange
        email_ids = [1, 2, 3]
        mock_filter_result = MagicMock()
        self.mock_session.query.return_value.filter.return_value = mock_filter_result

        # Act
        self.service.delete_emails(email_ids)

        # Assert
        self.mock_session.query.assert_called_once_with(EmailMessageDB)
        self.mock_session.query.return_value.filter.assert_called_once()
        mock_filter_result.delete.assert_called_once_with(synchronize_session=False)
        self.mock_session.commit.assert_called_once()
        self.signals.emails_changed.emit.assert_called_once()

    def test_delete_emails_empty_list(self):
        # Arrange
        email_ids = []

        # Act
        self.service.delete_emails(email_ids)

        # Assert - nothing should be called if list is empty
        self.mock_session.query.assert_not_called()
        self.mock_session.commit.assert_not_called()
        self.signals.emails_changed.emit.assert_not_called()

if __name__ == '__main__':
    unittest.main()
