"""Runtime settings merge helpers.

Environment variables define deployment defaults; rows in the ``settings``
table provide user-managed overrides for selected platform configuration.
"""

from __future__ import annotations

import base64
import hashlib
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from .config import Settings
from .models import Setting


def value_from_settings(db: Session, user_id: str, key: str, settings: Settings) -> Any:
    row = db.get(Setting, {"user_id": user_id, "key": key})
    if not row:
        return None
    return _deserialize_setting_value(row, settings)


def serialized_setting_value(value: Any, *, is_secret: bool, settings: Settings) -> dict[str, Any]:
    if not is_secret:
        return {"value": value}
    secret_value = str(value or "").strip()
    if not secret_value:
        return {"value": ""}
    return {"encrypted": _fernet(settings).encrypt(secret_value.encode("utf-8")).decode("utf-8")}


def effective_settings(settings: Settings, db: Session, user_id: str) -> Settings:
    return settings.model_copy(
        update={
            "apify_api_token": value_from_settings(db, user_id, "apify_api_key", settings) or settings.apify_api_token,
            "gemini_api_key": value_from_settings(db, user_id, "gemini_api_key", settings) or settings.gemini_api_key,
            "google_sheets_spreadsheet_id": value_from_settings(db, user_id, "google_sheets_id", settings)
            or settings.google_sheets_spreadsheet_id,
            "default_lead_limit": value_from_settings(db, user_id, "default_lead_limit", settings)
            or settings.default_lead_limit,
        }
    )


def _deserialize_setting_value(row: Setting, settings: Settings) -> Any:
    if not row.is_secret:
        return row.value.get("value")
    encrypted = row.value.get("encrypted")
    if encrypted:
        try:
            return _fernet(settings).decrypt(str(encrypted).encode("utf-8")).decode("utf-8")
        except (InvalidToken, ValueError):
            return None
    return row.value.get("value")


def _fernet(settings: Settings) -> Fernet:
    secret = settings.jwt_secret_key.strip()
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY or SESSION_SECRET is required to encrypt user settings")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)
