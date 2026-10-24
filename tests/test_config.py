import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import psycopg
from staging_core import ConfigurationError, SafetyError, Settings, connect


class SettingsTests(unittest.TestCase):
    def test_environment_is_supported_without_oracle_fallback(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            "STG_USER": "loader", "STG_PASSWORD": "test-not-a-real-secret", "ORACLE_PASSWORD": "ignored"
        }, clear=True):
            settings = Settings.from_env(Path(directory) / "absent")
        self.assertEqual((settings.host, settings.port, settings.database, settings.schema),
                         ("127.0.0.1", 5433, "chinook_staging", "public"))
        self.assertNotIn(settings.password, repr(settings))

    def test_dotenv_preserves_dollar_signs_without_interpolation(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            path = Path(directory) / ".env"
            path.write_text('STG_USER=loader\nSTG_PASSWORD="test${UNSET}_literal"\n', encoding="utf-8")
            self.assertEqual(Settings.from_env(path).password, "test${UNSET}_literal")

    def test_missing_credentials_are_explicit_and_never_guessed(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ConfigurationError, "STG_USER, STG_PASSWORD"):
                Settings.from_env(Path(directory) / "absent")

    def test_wrong_database_and_unsafe_schema_are_rejected(self):
        with self.assertRaises(SafetyError):
            Settings("localhost", 5433, "chinook_dw", "public", "loader", "test").validate()
        with self.assertRaises(ConfigurationError):
            Settings("localhost", 5433, "chinook_staging", 'public;DROP', "loader", "test").validate()

    def test_connection_errors_do_not_reveal_credentials(self):
        settings = Settings("localhost", 5433, "chinook_staging", "public", "loader", "test-hidden-secret")
        with patch("staging_core.psycopg.connect", side_effect=psycopg.OperationalError(settings.password)):
            with self.assertRaises(ConnectionError) as raised:
                connect(settings)
        self.assertNotIn(settings.password, str(raised.exception))


if __name__ == "__main__":
    unittest.main()
