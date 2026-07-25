"""Runtime settings merge helpers.

Environment variables define deployment defaults; rows in the ``settings``
table provide user-managed overrides for selected platform configuration.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .config import Settings
from .models import Setting


def value_from_settings(db: Session, user_id: str, key: str) -> Any:
    row = db.get(Setting, {"user_id": user_id, "key": key})
    if not row:
        return None
    return row.value.get("value")


def effective_settings(settings: Settings, db: Session, user_id: str) -> Settings:
    gmail = value_from_settings(db, user_id, "gmail_credentials") or {}
    return settings.model_copy(
        update={
            "apify_api_token": value_from_settings(db, user_id, "apify_api_key") or settings.apify_api_token,
            "gemini_api_key": value_from_settings(db, user_id, "gemini_api_key") or settings.gemini_api_key,
            "google_sheets_spreadsheet_id": value_from_settings(db, user_id, "google_sheets_id")
            or settings.google_sheets_spreadsheet_id,
            "default_lead_limit": value_from_settings(db, user_id, "default_lead_limit")
            or settings.default_lead_limit,
            "gmail_client_id": gmail.get("client_id") or settings.gmail_client_id,
            "gmail_client_secret": gmail.get("client_secret") or settings.gmail_client_secret,
            "gmail_refresh_token": gmail.get("refresh_token") or settings.gmail_refresh_token,
            "gmail_sender_email": gmail.get("sender_email") or settings.gmail_sender_email,
        }
    )
