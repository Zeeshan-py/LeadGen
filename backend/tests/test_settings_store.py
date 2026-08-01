"""Regression tests for encrypted user-managed settings."""

from __future__ import annotations

import unittest
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import Base
from app.models import Setting
from app.settings_store import serialized_setting_value, value_from_settings


class SettingsStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.settings = Settings(_env_file=None, JWT_SECRET_KEY="settings-secret-key")
        self.user_id = str(uuid.uuid4())

    def test_secret_setting_is_encrypted_at_rest(self) -> None:
        with Session(self.engine) as db:
            row = Setting(
                user_id=self.user_id,
                key="gemini_api_key",
                value=serialized_setting_value("gemini-secret", is_secret=True, settings=self.settings),
                is_secret=True,
            )
            db.add(row)
            db.commit()

            self.assertNotIn("gemini-secret", str(row.value))
            self.assertEqual(value_from_settings(db, self.user_id, "gemini_api_key", self.settings), "gemini-secret")

    def test_plaintext_legacy_secret_setting_still_reads(self) -> None:
        with Session(self.engine) as db:
            db.add(
                Setting(
                    user_id=self.user_id,
                    key="apify_api_key",
                    value={"value": "legacy-secret"},
                    is_secret=True,
                )
            )
            db.commit()

            self.assertEqual(value_from_settings(db, self.user_id, "apify_api_key", self.settings), "legacy-secret")


if __name__ == "__main__":
    unittest.main()
