"""Regression tests for per-user Gmail OAuth connections."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import Base
from app.gmail_connections import (
    GmailConnectionRequiredError,
    decrypt_refresh_token,
    disconnect_gmail_connection,
    encrypt_refresh_token,
    gmail_client_for_user,
    get_gmail_connection,
    upsert_gmail_connection,
)


class GmailConnectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.settings = Settings(
            _env_file=None,
            JWT_SECRET_KEY="test-secret-for-gmail-refresh-token-encryption",
            GMAIL_CLIENT_ID="gmail-client-id",
            GMAIL_CLIENT_SECRET="gmail-client-secret",
            GMAIL_REFRESH_TOKEN="legacy-global-refresh-token",
        )

    def test_refresh_token_is_encrypted_at_rest(self) -> None:
        encrypted = encrypt_refresh_token(self.settings, "user-refresh-token")

        self.assertNotEqual(encrypted, "user-refresh-token")
        self.assertEqual(decrypt_refresh_token(self.settings, encrypted), "user-refresh-token")

    def test_reconnect_replaces_existing_user_gmail_connection(self) -> None:
        with Session(self.engine) as db:
            first = upsert_gmail_connection(
                db,
                self.settings,
                user_id="00000000-0000-0000-0000-000000000001",
                gmail_email="first@example.test",
                refresh_token="first-refresh-token",
                scopes="https://www.googleapis.com/auth/gmail.send",
            )
            first_id = first.id
            upsert_gmail_connection(
                db,
                self.settings,
                user_id="00000000-0000-0000-0000-000000000001",
                gmail_email="second@example.test",
                refresh_token="second-refresh-token",
                scopes="https://www.googleapis.com/auth/gmail.send",
            )
            db.commit()

            connection = get_gmail_connection(db, "00000000-0000-0000-0000-000000000001")

        self.assertIsNotNone(connection)
        self.assertEqual(connection.id, first_id)
        self.assertEqual(connection.gmail_email, "second@example.test")
        self.assertEqual(
            decrypt_refresh_token(self.settings, connection.refresh_token_encrypted),
            "second-refresh-token",
        )

    def test_disconnect_clears_refresh_token(self) -> None:
        with Session(self.engine) as db:
            upsert_gmail_connection(
                db,
                self.settings,
                user_id="00000000-0000-0000-0000-000000000001",
                gmail_email="user@example.test",
                refresh_token="user-refresh-token",
                scopes="https://www.googleapis.com/auth/gmail.send",
            )
            connection = disconnect_gmail_connection(
                db,
                user_id="00000000-0000-0000-0000-000000000001",
            )
            db.commit()
            is_connected = connection.is_connected if connection else None
            encrypted_token = connection.refresh_token_encrypted if connection else None

        self.assertIsNotNone(connection)
        self.assertFalse(is_connected)
        self.assertEqual(encrypted_token, "")

    @patch("app.gmail_connections.GmailClient")
    def test_gmail_client_uses_user_refresh_token_not_global_refresh_token(self, gmail_class: MagicMock) -> None:
        gmail_class.return_value.profile_email = "user@example.test"

        with Session(self.engine) as db:
            upsert_gmail_connection(
                db,
                self.settings,
                user_id="00000000-0000-0000-0000-000000000001",
                gmail_email="user@example.test",
                refresh_token="user-refresh-token",
                scopes="https://www.googleapis.com/auth/gmail.send",
            )
            gmail_client_for_user(db, self.settings, "00000000-0000-0000-0000-000000000001")

        gmail_class.assert_called_once_with(
            "gmail-client-id",
            "gmail-client-secret",
            "user-refresh-token",
        )

    def test_gmail_client_requires_user_connection(self) -> None:
        with Session(self.engine) as db:
            with self.assertRaisesRegex(
                GmailConnectionRequiredError,
                "Please connect your Gmail account",
            ):
                gmail_client_for_user(db, self.settings, "00000000-0000-0000-0000-000000000001")


if __name__ == "__main__":
    unittest.main()
