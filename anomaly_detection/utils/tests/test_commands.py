"""
Test custom Django management command.
"""

# Path is used (here) to mock the behaviour of the database
from unittest.mock import patch

from psycopg import OperationalError as PsycopgError

from django.core.management import call_command
from django.db.utils import OperationalError
from django.test import SimpleTestCase


# Mock the "check" method used in the Command class of
# the wait_for_db command.
@patch("anomaly_detection.utils.management.commands.wait_for_db.Command.check")
class CommandTest(SimpleTestCase):
    """Test commands."""

    def test_wait_for_db_ready(self, patched_check):
        """Test waiting for database if database ready."""
        # When "check" is called inside our command (inside our test case),
        # it will return True.
        patched_check.return_value = True

        # It calls the specified command
        call_command('wait_for_db')

        # It checks if we call the "check" method with these parameters.
        patched_check.assert_called_once_with(databases=['default'])

    # Mock / overwriting the sleep function used in the command
    @patch('time.sleep')
    def test_wait_for_db_delay(self, patched_sleep, patched_check):
        """Test waiting for database when getting OperationalError."""
        # The first two times its called, it will raise a Psycop2 Error,
        # the next three times, it will raise an Operational Error and
        # the last time will returns True.
        patched_check.side_effect = [PsycopgError] * 2 \
            + [OperationalError] * 3 + [True]

        call_command('wait_for_db')

        self.assertEqual(patched_check.call_count, 6)
        patched_check.assert_called_with(databases=['default'])
