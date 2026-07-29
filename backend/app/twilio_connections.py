"""Per-user Twilio connection and AI voice preference helpers."""

from __future__ import annotations

import base64
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ai_sdr.config import AISDRSettings

from .config import Settings
from .models import TwilioConnection, VoiceSettings

logger = logging.getLogger(__name__)

VOICE_SPEEDS = {"slowest", "slower", "normal", "faster", "fastest"}


class TwilioConnectionError(RuntimeError):
    pass


class TwilioConnectionRequiredError(TwilioConnectionError):
    pass


class TwilioPhoneSelectionRequired(TwilioConnectionError):
    def __init__(self, numbers: list["TwilioPhoneNumber"]) -> None:
        super().__init__("Select which Twilio phone number LeadForge should use for AI SDR calls.")
        self.numbers = numbers


@dataclass(frozen=True)
class TwilioPhoneNumber:
    phone_sid: str
    phone_number: str
    friendly_name: str = ""


def get_active_twilio_connection(db: Session, user_id: str) -> TwilioConnection | None:
    return db.scalar(
        select(TwilioConnection)
        .where(
            TwilioConnection.user_id == user_id,
            TwilioConnection.is_active.is_(True),
        )
        .order_by(desc(TwilioConnection.connected_at), desc(TwilioConnection.created_at))
        .limit(1)
    )


def get_connected_twilio_connection(db: Session, user_id: str) -> TwilioConnection | None:
    return db.scalar(
        select(TwilioConnection)
        .where(
            TwilioConnection.user_id == user_id,
            TwilioConnection.is_active.is_(True),
            TwilioConnection.is_connected.is_(True),
        )
        .order_by(desc(TwilioConnection.connected_at), desc(TwilioConnection.created_at))
        .limit(1)
    )


def validate_twilio_credentials(
    *,
    account_sid: str,
    auth_token: str,
    timeout_seconds: int = 15,
) -> tuple[str, list[TwilioPhoneNumber]]:
    account_sid = account_sid.strip()
    auth_token = auth_token.strip()
    if not account_sid.startswith("AC"):
        raise TwilioConnectionError("Invalid Twilio Account SID. Twilio Account SIDs start with AC.")
    if not auth_token:
        raise TwilioConnectionError("Twilio Auth Token is required.")

    try:
        from twilio.base.exceptions import TwilioException, TwilioRestException
        from twilio.http.http_client import TwilioHttpClient
        from twilio.rest import Client
    except ImportError as exc:
        raise TwilioConnectionError("Twilio package is not installed on the server.") from exc

    try:
        http_client = TwilioHttpClient(timeout=timeout_seconds)
        client = Client(account_sid, auth_token, http_client=http_client)
        account = client.api.accounts(account_sid).fetch()
        numbers = client.incoming_phone_numbers.list(limit=50)
    except TwilioRestException as exc:
        raise TwilioConnectionError(_friendly_twilio_error(exc)) from exc
    except TwilioException as exc:
        raise TwilioConnectionError("Twilio API is unavailable. Try again in a moment.") from exc
    except Exception as exc:
        logger.warning("Twilio credential validation failed: %s", exc)
        raise TwilioConnectionError("Twilio validation failed. Check the Account SID and Auth Token.") from exc

    phone_numbers = [
        TwilioPhoneNumber(
            phone_sid=str(getattr(number, "sid", "") or ""),
            phone_number=str(getattr(number, "phone_number", "") or ""),
            friendly_name=str(getattr(number, "friendly_name", "") or ""),
        )
        for number in numbers
        if str(getattr(number, "phone_number", "") or "")
    ]
    if not phone_numbers:
        raise TwilioConnectionError("No Twilio phone numbers found in this account.")
    return str(getattr(account, "status", "") or ""), phone_numbers


def upsert_twilio_connection(
    db: Session,
    settings: Settings,
    *,
    user_id: str,
    account_sid: str,
    auth_token: str,
    account_status: str,
    phone_numbers: list[TwilioPhoneNumber],
    selected_phone_sid: str = "",
    selected_phone_number: str = "",
) -> TwilioConnection:
    selected = _select_phone_number(phone_numbers, selected_phone_sid, selected_phone_number)
    now = datetime.now(timezone.utc)
    for existing in db.scalars(
        select(TwilioConnection).where(
            TwilioConnection.user_id == user_id,
            TwilioConnection.is_active.is_(True),
        )
    ):
        existing.is_active = False
        existing.is_connected = False
        existing.disconnected_at = now
        db.add(existing)

    connection = TwilioConnection(user_id=user_id)
    connection.account_sid = account_sid.strip()
    connection.auth_token_encrypted = encrypt_twilio_auth_token(settings, auth_token)
    connection.phone_number = selected.phone_number
    connection.phone_sid = selected.phone_sid
    connection.friendly_name = selected.friendly_name
    connection.account_status = account_status
    connection.is_connected = True
    connection.is_active = True
    connection.connected_at = now
    connection.disconnected_at = None
    connection.last_health_check_at = now
    connection.last_error = ""
    db.add(connection)
    db.flush()
    return connection


def disconnect_twilio_connection(db: Session, *, user_id: str) -> TwilioConnection | None:
    connection = get_active_twilio_connection(db, user_id)
    if not connection:
        return None
    connection.is_connected = False
    connection.is_active = False
    connection.auth_token_encrypted = ""
    connection.disconnected_at = datetime.now(timezone.utc)
    connection.last_error = ""
    db.add(connection)
    db.flush()
    return connection


def check_twilio_connection(db: Session, settings: Settings, *, user_id: str) -> TwilioConnection:
    connection = get_connected_twilio_connection(db, user_id)
    if not connection or not connection.auth_token_encrypted:
        raise TwilioConnectionRequiredError("Connect Twilio in Settings before starting AI SDR calls.")
    try:
        auth_token = decrypt_twilio_auth_token(settings, connection.auth_token_encrypted)
        account_status, phone_numbers = validate_twilio_credentials(
            account_sid=connection.account_sid,
            auth_token=auth_token,
        )
        selected = _select_phone_number(phone_numbers, connection.phone_sid, connection.phone_number)
    except (TwilioConnectionError, InvalidToken) as exc:
        connection.is_connected = False
        connection.last_error = str(exc)
        connection.disconnected_at = datetime.now(timezone.utc)
        db.add(connection)
        db.flush()
        raise TwilioConnectionError("Twilio authorization is invalid. Reconnect Twilio in Settings.") from exc

    connection.phone_number = selected.phone_number
    connection.phone_sid = selected.phone_sid
    connection.friendly_name = selected.friendly_name
    connection.account_status = account_status
    connection.last_health_check_at = datetime.now(timezone.utc)
    connection.last_error = ""
    db.add(connection)
    db.flush()
    return connection


def get_voice_settings(db: Session, user_id: str) -> VoiceSettings | None:
    return db.scalar(select(VoiceSettings).where(VoiceSettings.user_id == user_id).limit(1))


def upsert_voice_settings(
    db: Session,
    settings: Settings,
    *,
    user_id: str,
    voice_provider: str = "cartesia",
    voice_id: str = "",
    voice_name: str = "",
    speaking_speed: str = "normal",
    language: str = "en",
    ai_greeting: str = "",
    business_name: str = "",
    assistant_name: str = "",
    cartesia_api_key: str = "",
) -> VoiceSettings:
    provider = voice_provider.strip().lower() or "cartesia"
    if provider != "cartesia":
        raise TwilioConnectionError("Cartesia is the only supported voice provider right now.")
    speed = speaking_speed.strip().lower() or "normal"
    if speed not in VOICE_SPEEDS:
        raise TwilioConnectionError("Speaking speed must be slowest, slower, normal, faster, or fastest.")
    record = get_voice_settings(db, user_id) or VoiceSettings(user_id=user_id)
    record.voice_provider = provider
    record.voice_id = voice_id.strip()
    record.voice_name = voice_name.strip()
    record.speaking_speed = speed
    record.language = (language.strip() or "en")[:20]
    record.ai_greeting = ai_greeting.strip()
    record.business_name = business_name.strip()
    record.assistant_name = assistant_name.strip()
    if cartesia_api_key.strip():
        record.cartesia_api_key_encrypted = encrypt_twilio_auth_token(settings, cartesia_api_key.strip())
    db.add(record)
    db.flush()
    return record


def ai_sdr_settings_for_user(
    db: Session,
    settings: Settings,
    base_settings: AISDRSettings,
    *,
    user_id: str,
) -> AISDRSettings:
    connection = get_connected_twilio_connection(db, user_id)
    if not connection or not connection.auth_token_encrypted:
        raise TwilioConnectionRequiredError("Connect Twilio in Settings before starting AI SDR calls.")

    try:
        auth_token = decrypt_twilio_auth_token(settings, connection.auth_token_encrypted)
    except InvalidToken as exc:
        connection.is_connected = False
        connection.last_error = "Twilio authorization is invalid. Reconnect Twilio in Settings."
        connection.disconnected_at = datetime.now(timezone.utc)
        db.add(connection)
        db.flush()
        raise TwilioConnectionRequiredError(connection.last_error) from exc

    updates: dict[str, Any] = {
        "twilio_account_sid": connection.account_sid,
        "twilio_auth_token": auth_token,
        "call_from_number": connection.phone_number,
    }
    voice = get_voice_settings(db, user_id)
    if voice:
        updates.update(
            {
                "speech_provider": voice.voice_provider or base_settings.speech_provider,
                "cartesia_voice_id": voice.voice_id or base_settings.cartesia_voice_id,
                "cartesia_language": voice.language or base_settings.cartesia_language,
                "cartesia_tts_speed": voice.speaking_speed or base_settings.cartesia_tts_speed,
                "assistant_name": voice.assistant_name,
                "assistant_business_name": voice.business_name,
                "ai_greeting": voice.ai_greeting,
            }
        )
        if voice.cartesia_api_key_encrypted:
            try:
                updates["cartesia_api_key"] = decrypt_twilio_auth_token(settings, voice.cartesia_api_key_encrypted)
            except InvalidToken as exc:
                raise TwilioConnectionRequiredError("Cartesia API key is invalid. Save Voice Settings again.") from exc
    return base_settings.model_copy(update=updates)


def mask_secret(value: str, *, visible_prefix: int = 2, visible_suffix: int = 4) -> str:
    value = value.strip()
    if not value:
        return ""
    if len(value) <= visible_prefix + visible_suffix:
        return "*" * len(value)
    return f"{value[:visible_prefix]}{'*' * max(8, len(value) - visible_prefix - visible_suffix)}{value[-visible_suffix:]}"


def encrypt_twilio_auth_token(settings: Settings, auth_token: str) -> str:
    return _fernet(settings).encrypt(auth_token.encode("utf-8")).decode("utf-8")


def decrypt_twilio_auth_token(settings: Settings, encrypted_auth_token: str) -> str:
    return _fernet(settings).decrypt(encrypted_auth_token.encode("utf-8")).decode("utf-8")


def _select_phone_number(
    phone_numbers: list[TwilioPhoneNumber],
    selected_phone_sid: str = "",
    selected_phone_number: str = "",
) -> TwilioPhoneNumber:
    if not phone_numbers:
        raise TwilioConnectionError("No Twilio phone numbers found in this account.")
    selected_phone_sid = selected_phone_sid.strip()
    selected_phone_number = selected_phone_number.strip()
    if selected_phone_sid or selected_phone_number:
        for number in phone_numbers:
            if selected_phone_sid and number.phone_sid == selected_phone_sid:
                return number
            if selected_phone_number and number.phone_number == selected_phone_number:
                return number
        raise TwilioConnectionError("Selected phone number does not belong to this Twilio account.")
    if len(phone_numbers) == 1:
        return phone_numbers[0]
    raise TwilioPhoneSelectionRequired(phone_numbers)


def _fernet(settings: Settings) -> Fernet:
    secret = settings.jwt_secret_key.strip()
    if not secret:
        raise TwilioConnectionError("Set JWT_SECRET_KEY or SESSION_SECRET before connecting Twilio.")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def _friendly_twilio_error(exc: Exception) -> str:
    status = getattr(exc, "status", None)
    code = getattr(exc, "code", None)
    if status in {401, 403} or code in {20003, 20404}:
        return "Invalid Twilio Account SID or Auth Token."
    if status in {408, 429, 500, 502, 503, 504}:
        return "Twilio API is temporarily unavailable. Try again in a moment."
    message = str(getattr(exc, "msg", "") or exc).strip()
    return message[:300] or "Twilio validation failed."
