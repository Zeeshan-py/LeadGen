"""Regression tests for cross-cutting security controls."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.rate_limit import clear_rate_limits_for_tests, enforce_rate_limit
from lead_automation.url_safety import is_safe_public_url
from lead_automation.validation import normalize_website


class SecurityControlsTests(unittest.TestCase):
    def tearDown(self) -> None:
        clear_rate_limits_for_tests()

    def test_public_url_safety_blocks_private_and_local_targets(self) -> None:
        self.assertFalse(is_safe_public_url("http://localhost:8000", resolve=False))
        self.assertFalse(is_safe_public_url("http://127.0.0.1/admin", resolve=False))
        self.assertFalse(is_safe_public_url("http://169.254.169.254/latest/meta-data", resolve=False))
        self.assertFalse(is_safe_public_url("file:///etc/passwd", resolve=False))
        self.assertTrue(is_safe_public_url("https://example.org/", resolve=False))

    def test_public_url_safety_blocks_hosts_that_resolve_private(self) -> None:
        with patch("lead_automation.url_safety.socket.getaddrinfo") as getaddrinfo:
            getaddrinfo.return_value = [(0, 0, 0, "", ("10.0.0.5", 443))]
            self.assertFalse(is_safe_public_url("https://public-name.example/", resolve=True))

    def test_normalize_website_rejects_ssrf_targets(self) -> None:
        self.assertEqual(normalize_website("127.0.0.1:8000"), "")
        self.assertEqual(normalize_website("https://10.0.0.10/"), "")
        self.assertEqual(normalize_website("https://example.org/contact"), "https://example.org/contact")

    def test_rate_limiter_returns_429_after_limit(self) -> None:
        enforce_rate_limit("test:limit", limit=2, window_seconds=60)
        enforce_rate_limit("test:limit", limit=2, window_seconds=60)

        with self.assertRaises(HTTPException) as raised:
            enforce_rate_limit("test:limit", limit=2, window_seconds=60)

        self.assertEqual(raised.exception.status_code, 429)
        self.assertGreaterEqual(int(raised.exception.headers["Retry-After"]), 1)


if __name__ == "__main__":
    unittest.main()
