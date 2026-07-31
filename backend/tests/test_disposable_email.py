"""Tests for disposable email signup protection."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import httpx
from fastapi import HTTPException, Response
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.auth_routes import SignUpRequest, signup
from app.config import Settings
from app.database import Base
from app.disposable_email import (
    DISPOSABLE_EMAIL_REJECTION,
    DisposableEmailRejected,
    clear_abstract_email_cache,
    ensure_signup_email_allowed,
    is_disposable_domain,
    replace_disposable_domains_for_tests,
)
from app.models import User


class FakeAbstractResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://emailreputation.abstractapi.com/v1")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("Abstract error", request=request, response=response)

    def json(self) -> dict:
        return self.payload


class FakeAbstractClient:
    def __init__(self, response: FakeAbstractResponse | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls = 0

    def __enter__(self) -> "FakeAbstractClient":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def get(self, *args, **kwargs) -> FakeAbstractResponse:
        self.calls += 1
        if self.error:
            raise self.error
        assert self.response is not None
        return self.response


class DisposableEmailTests(unittest.TestCase):
    def tearDown(self) -> None:
        replace_disposable_domains_for_tests(set())
        clear_abstract_email_cache()

    def test_blocklist_matches_exact_domain_and_subdomain(self) -> None:
        replace_disposable_domains_for_tests({"mailinator.com"})

        self.assertTrue(is_disposable_domain("mailinator.com"))
        self.assertTrue(is_disposable_domain("inbox.mailinator.com"))
        self.assertFalse(is_disposable_domain("example.com"))

    def test_abstract_disposable_response_rejects_signup_email(self) -> None:
        replace_disposable_domains_for_tests(set())
        settings = Settings(_env_file=None, ABSTRACT_EMAIL_API_KEY="abstract-test-key")
        client = FakeAbstractClient(
            FakeAbstractResponse({"email_quality": {"is_disposable": True}})
        )

        with patch("app.disposable_email.httpx.Client", return_value=client):
            with self.assertRaises(DisposableEmailRejected) as raised:
                ensure_signup_email_allowed("person@example.com", settings)

        self.assertEqual(str(raised.exception), DISPOSABLE_EMAIL_REJECTION)

    def test_successful_abstract_response_is_cached(self) -> None:
        replace_disposable_domains_for_tests(set())
        settings = Settings(_env_file=None, ABSTRACT_EMAIL_API_KEY="abstract-test-key")
        client = FakeAbstractClient(
            FakeAbstractResponse({"email_quality": {"is_disposable": False}})
        )

        with patch("app.disposable_email.httpx.Client", return_value=client):
            ensure_signup_email_allowed("person@example.com", settings)
            ensure_signup_email_allowed("person@example.com", settings)

        self.assertEqual(client.calls, 1)

    def test_abstract_failure_allows_signup(self) -> None:
        replace_disposable_domains_for_tests(set())
        settings = Settings(_env_file=None, ABSTRACT_EMAIL_API_KEY="abstract-test-key")
        client = FakeAbstractClient(error=httpx.ConnectError("temporary outage"))

        with patch("app.disposable_email.httpx.Client", return_value=client):
            ensure_signup_email_allowed("person@example.com", settings)

        self.assertEqual(client.calls, 1)

    def test_signup_rejects_blocklisted_email_before_user_creation(self) -> None:
        replace_disposable_domains_for_tests({"mailinator.com"})
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)

        with Session(engine) as db:
            with self.assertRaises(HTTPException) as raised:
                signup(
                    SignUpRequest(
                        full_name="Disposable User",
                        email="user@mailinator.com",
                        password="Password123!",
                    ),
                    _request(),
                    Response(),
                    db,
                    Settings(_env_file=None),
                )
            saved_user = db.scalar(select(User).limit(1))

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, DISPOSABLE_EMAIL_REJECTION)
        self.assertIsNone(saved_user)


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/auth/signup",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "scheme": "http",
            "server": ("testserver", 80),
        }
    )


if __name__ == "__main__":
    unittest.main()
