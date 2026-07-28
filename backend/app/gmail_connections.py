"""Per-user Gmail OAuth connection helpers.

Gmail outreach uses the deployment-wide Gmail OAuth client but stores each
authenticated user's refresh token separately. Access tokens are never persisted;
Google credentials refresh them in memory whenever Gmail is used.
"""

from __future__ import annotations

import base64
import hashlib
import logging
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .gmail import GmailClient, GmailConfigurationError
from .models import GmailConnection

logger = logging.getLogger(__name__)


class GmailConnectionRequiredError(RuntimeError):
    pass


def gmail_redirect_uri(settings: Settings) -> str:
    return f"{settings.public_backend_url.rstrip('/')}/gmail/callback"


def get_gmail_connection(db: Session, user_id: str) -> GmailConnection | None:
    return db.scalar(select(GmailConnection).where(GmailConnection.user_id == user_id).limit(1))


def get_connected_gmail_connection(db: Session, user_id: str) -> GmailConnection | None:
    return db.scalar(
        select(GmailConnection)
        .where(GmailConnection.user_id == user_id, GmailConnection.is_connected.is_(True))
        .limit(1)
    )


def upsert_gmail_connection(
    db: Session,
    settings: Settings,
    *,
    user_id: str,
    gmail_email: str,
    refresh_token: str,
    scopes: str,
) -> GmailConnection:
    if not refresh_token:
        raise GmailConfigurationError(
            "Google did not return a Gmail refresh token. Reconnect Gmail and approve offline access."
        )

    now = datetime.now(timezone.utc)
    connection = get_gmail_connection(db, user_id)
    if connection is None:
        connection = GmailConnection(user_id=user_id)

    connection.gmail_email = gmail_email.strip().lower()
    connection.refresh_token_encrypted = encrypt_refresh_token(settings, refresh_token)
    connection.scopes = scopes
    connection.is_connected = True
    connection.connected_at = now
    connection.disconnected_at = None
    connection.last_health_check_at = now
    connection.last_error = ""
    db.add(connection)
    db.flush()
    return connection


def disconnect_gmail_connection(db: Session, *, user_id: str) -> GmailConnection | None:
    connection = get_gmail_connection(db, user_id)
    if not connection:
        return None
    connection.is_connected = False
    connection.refresh_token_encrypted = ""
    connection.disconnected_at = datetime.now(timezone.utc)
    connection.last_error = ""
    db.add(connection)
    db.flush()
    return connection


def gmail_client_for_user(db: Session, settings: Settings, user_id: str) -> GmailClient:
    if not settings.gmail_client_id or not settings.gmail_client_secret:
        raise GmailConfigurationError("Gmail OAuth is not configured. Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET.")

    connection = get_connected_gmail_connection(db, user_id)
    if not connection or not connection.refresh_token_encrypted:
        raise GmailConnectionRequiredError("Please connect your Gmail account before sending emails.")

    try:
        refresh_token = decrypt_refresh_token(settings, connection.refresh_token_encrypted)
        gmail = GmailClient(settings.gmail_client_id, settings.gmail_client_secret, refresh_token)
        gmail.validate_configuration()
    except (GmailConfigurationError, InvalidToken) as exc:
        connection.is_connected = False
        connection.last_error = "Gmail authorization is invalid or expired. Reconnect Gmail in Settings."
        connection.disconnected_at = datetime.now(timezone.utc)
        db.add(connection)
        db.commit()
        logger.warning("Gmail connection invalid for user_id=%s: %s", user_id, exc)
        raise GmailConfigurationError(connection.last_error) from exc

    connection.gmail_email = gmail.profile_email.strip().lower() or connection.gmail_email
    connection.last_health_check_at = datetime.now(timezone.utc)
    connection.last_error = ""
    db.add(connection)
    db.flush()
    return gmail


def encrypt_refresh_token(settings: Settings, refresh_token: str) -> str:
    return _fernet(settings).encrypt(refresh_token.encode("utf-8")).decode("utf-8")


def decrypt_refresh_token(settings: Settings, encrypted_refresh_token: str) -> str:
    return _fernet(settings).decrypt(encrypted_refresh_token.encode("utf-8")).decode("utf-8")


def _fernet(settings: Settings) -> Fernet:
    secret = settings.jwt_secret_key.strip()
    if not secret:
        raise GmailConfigurationError("Set JWT_SECRET_KEY or SESSION_SECRET before connecting Gmail.")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)
