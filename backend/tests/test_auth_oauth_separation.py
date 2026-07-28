"""Regression tests for separate Google login and Gmail outreach OAuth clients."""

from __future__ import annotations

import unittest
from urllib.parse import parse_qs, urlparse

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.auth_routes import _upsert_oauth_user, google_login
from app.config import Settings
from app.database import Base
from app.models import User


class GoogleOAuthSeparationTests(unittest.TestCase):
    def test_google_login_uses_google_oauth_credentials_not_gmail_credentials(self) -> None:
        settings = Settings(
            _env_file=None,
            GOOGLE_OAUTH_CLIENT_ID="google-login-client",
            GOOGLE_OAUTH_CLIENT_SECRET="google-login-secret",
            GOOGLE_OAUTH_REDIRECT_URI="https://leadforage.up.railway.app/auth/google/callback",
            GMAIL_CLIENT_ID="gmail-outreach-client",
            GMAIL_CLIENT_SECRET="gmail-outreach-secret",
            GMAIL_REFRESH_TOKEN="gmail-refresh-token",
            GMAIL_SENDER_EMAIL="sender@example.test",
        )

        response = google_login(request=None, next="/dashboard", settings=settings)

        location = response.headers["location"]
        query = parse_qs(urlparse(location).query)
        self.assertEqual(query["client_id"], ["google-login-client"])
        self.assertNotEqual(query["client_id"], ["gmail-outreach-client"])
        self.assertEqual(
            query["redirect_uri"],
            ["https://leadforage.up.railway.app/auth/google/callback"],
        )
        self.assertEqual(query["scope"], ["openid email profile"])

    def test_google_login_accepts_compatibility_aliases(self) -> None:
        settings = Settings(
            _env_file=None,
            GOOGLE_CLIENT_ID="google-login-client",
            GOOGLE_CLIENT_SECRET="google-login-secret",
            GOOGLE_REDIRECT_URI="https://leadforage.up.railway.app/auth/google/callback",
        )

        response = google_login(request=None, next="/dashboard", settings=settings)

        query = parse_qs(urlparse(response.headers["location"]).query)
        self.assertEqual(query["client_id"], ["google-login-client"])
        self.assertEqual(
            query["redirect_uri"],
            ["https://leadforage.up.railway.app/auth/google/callback"],
        )

    def test_oauth_upsert_omits_avatar_urls_that_exceed_storage_limit(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)

        with Session(engine) as db:
            user = _upsert_oauth_user(
                db,
                provider="google",
                provider_id="google-user-id",
                email="oauth-user@example.test",
                full_name="OAuth User",
                avatar_url="https://lh3.googleusercontent.com/" + ("a" * 1000),
                is_verified=True,
                settings=Settings(_env_file=None),
            )
            db.commit()

            saved = db.scalar(select(User).where(User.id == user.id))

        self.assertIsNotNone(saved)
        self.assertEqual(saved.avatar_url, "")
        self.assertEqual(saved.email, "oauth-user@example.test")
        self.assertEqual(saved.provider, "google")


if __name__ == "__main__":
    unittest.main()
