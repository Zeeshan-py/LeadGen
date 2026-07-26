"""Regression tests for separate Google login and Gmail outreach OAuth clients."""

from __future__ import annotations

import unittest
from urllib.parse import parse_qs, urlparse

from app.auth_routes import google_login
from app.config import Settings


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


if __name__ == "__main__":
    unittest.main()
