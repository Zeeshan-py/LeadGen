from __future__ import annotations

import json
import logging
import unittest
from unittest.mock import patch

from app.config import Settings
from app.google_sheets import (
    GoogleSheetsConfigError,
    _validate_google_sheets,
    load_google_credentials,
)


def _settings(service_account_json: str) -> Settings:
    return Settings(
        _env_file=None,
        GOOGLE_SHEETS_SPREADSHEET_ID="spreadsheet-id",
        GOOGLE_SERVICE_ACCOUNT_JSON=service_account_json,
    )


class GoogleSheetsCredentialTests(unittest.TestCase):
    def test_missing_json_disables_google_sheets_with_warning(self) -> None:
        logger = logging.getLogger("test.google-sheets")

        with self.assertLogs(logger, level=logging.WARNING) as captured:
            result = _validate_google_sheets(
                Settings(_env_file=None, GOOGLE_SERVICE_ACCOUNT_JSON=""),
                logger,
            )

        self.assertFalse(result.google_sheets)
        self.assertFalse(result.spreadsheet_access)
        self.assertEqual(result.code, "missing_credentials")
        self.assertFalse(result.spreadsheet_id_configured)
        self.assertIn("Google Sheets is disabled", result.message)
        self.assertIn(
            "GOOGLE_SERVICE_ACCOUNT_JSON is missing",
            "\n".join(captured.output),
        )

    def test_invalid_json_is_rejected(self) -> None:
        for value in ("not-json", "[]", '"text"'):
            with self.subTest(value=value):
                with self.assertRaises(GoogleSheetsConfigError) as raised:
                    load_google_credentials(_settings(value))

                self.assertEqual(raised.exception.code, "invalid_json")

    def test_credentials_are_created_from_service_account_info(self) -> None:
        info = {
            "type": "service_account",
            "client_email": "railway@example.test",
        }
        expected_credentials = object()

        with patch(
            "app.google_sheets.Credentials.from_service_account_info",
            return_value=expected_credentials,
        ) as from_info:
            credentials, source, parsed_info = load_google_credentials(
                _settings(json.dumps(info))
            )

        self.assertIs(credentials, expected_credentials)
        self.assertEqual(source, "GOOGLE_SERVICE_ACCOUNT_JSON")
        self.assertEqual(parsed_info, info)
        from_info.assert_called_once()


if __name__ == "__main__":
    unittest.main()
