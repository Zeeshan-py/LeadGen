"""Twilio connection and voice settings routes for AI SDR."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .auth import get_current_user
from .config import Settings, get_settings
from .database import get_db
from .models import TwilioConnection, User, VoiceSettings
from .schemas import (
    TwilioConnectRequest,
    TwilioConnectionStatus,
    TwilioPhoneNumberOption,
    VoiceSettingsPayload,
    VoiceSettingsStatus,
)
from .twilio_connections import (
    TwilioConnectionError,
    TwilioPhoneNumber,
    TwilioPhoneSelectionRequired,
    check_twilio_connection,
    disconnect_twilio_connection,
    get_active_twilio_connection,
    get_voice_settings,
    mask_secret,
    upsert_twilio_connection,
    upsert_voice_settings,
    validate_twilio_credentials,
)
from .subscription_access import require_feature_dependency

router = APIRouter(prefix="/twilio", tags=["twilio"], dependencies=[Depends(require_feature_dependency("twilio"))])


@router.get("/status", response_model=TwilioConnectionStatus)
def twilio_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TwilioConnectionStatus:
    return _twilio_status(get_active_twilio_connection(db, current_user.id))


@router.post("/connect", response_model=TwilioConnectionStatus)
def connect_twilio(
    payload: TwilioConnectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> TwilioConnectionStatus:
    try:
        account_status, phone_numbers = validate_twilio_credentials(
            account_sid=payload.account_sid,
            auth_token=payload.auth_token,
        )
        connection = upsert_twilio_connection(
            db,
            settings,
            user_id=current_user.id,
            account_sid=payload.account_sid,
            auth_token=payload.auth_token,
            account_status=account_status,
            phone_numbers=phone_numbers,
            selected_phone_sid=payload.phone_sid,
            selected_phone_number=payload.phone_number,
        )
        db.commit()
        return _twilio_status(connection, health="ok")
    except TwilioPhoneSelectionRequired as exc:
        db.rollback()
        return _twilio_status(
            get_active_twilio_connection(db, current_user.id),
            health="phone_selection_required",
            requires_phone_selection=True,
            phone_numbers=exc.numbers,
        )
    except TwilioConnectionError as exc:
        db.rollback()
        raise HTTPException(status_code=_twilio_error_status(str(exc)), detail=str(exc)) from exc


@router.post("/check", response_model=TwilioConnectionStatus)
def check_twilio(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> TwilioConnectionStatus:
    try:
        connection = check_twilio_connection(db, settings, user_id=current_user.id)
        db.commit()
        return _twilio_status(connection, health="ok")
    except TwilioConnectionError as exc:
        db.rollback()
        connection = get_active_twilio_connection(db, current_user.id)
        if connection:
            connection.last_error = str(exc)
            db.add(connection)
            db.commit()
        raise HTTPException(status_code=_twilio_error_status(str(exc)), detail=str(exc)) from exc


@router.delete("/disconnect", response_model=TwilioConnectionStatus)
def disconnect_twilio(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TwilioConnectionStatus:
    connection = disconnect_twilio_connection(db, user_id=current_user.id)
    db.commit()
    return _twilio_status(connection)


@router.get("/voice-settings", response_model=VoiceSettingsStatus)
def get_user_voice_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VoiceSettingsStatus:
    return _voice_settings_status(get_voice_settings(db, current_user.id))


@router.put("/voice-settings", response_model=VoiceSettingsStatus)
def save_user_voice_settings(
    payload: VoiceSettingsPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> VoiceSettingsStatus:
    try:
        voice = upsert_voice_settings(
            db,
            settings,
            user_id=current_user.id,
            voice_provider=payload.voice_provider,
            voice_id=payload.voice_id,
            voice_name=payload.voice_name,
            speaking_speed=payload.speaking_speed,
            language=payload.language,
            ai_greeting=payload.ai_greeting,
            business_name=payload.business_name,
            assistant_name=payload.assistant_name,
            cartesia_api_key=payload.cartesia_api_key,
        )
        db.commit()
        return _voice_settings_status(voice)
    except TwilioConnectionError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _twilio_status(
    connection: TwilioConnection | None,
    *,
    health: str | None = None,
    requires_phone_selection: bool = False,
    phone_numbers: list[TwilioPhoneNumber] | None = None,
) -> TwilioConnectionStatus:
    if not connection:
        return TwilioConnectionStatus(
            is_connected=False,
            health=health or "disconnected",
            requires_phone_selection=requires_phone_selection,
            phone_numbers=_phone_options(phone_numbers or []),
        )
    current_health = health or ("connected" if connection.is_connected else "disconnected")
    if connection.last_error:
        current_health = "error"
    return TwilioConnectionStatus(
        is_connected=connection.is_connected,
        account_sid_masked=mask_secret(connection.account_sid),
        phone_number=connection.phone_number,
        phone_sid=connection.phone_sid,
        friendly_name=connection.friendly_name,
        account_status=connection.account_status,
        connected_at=connection.connected_at,
        disconnected_at=connection.disconnected_at,
        health=current_health,
        last_health_check_at=connection.last_health_check_at,
        last_error=connection.last_error,
        requires_phone_selection=requires_phone_selection,
        phone_numbers=_phone_options(phone_numbers or []),
    )


def _voice_settings_status(settings: VoiceSettings | None) -> VoiceSettingsStatus:
    if not settings:
        return VoiceSettingsStatus()
    return VoiceSettingsStatus(
        voice_provider=settings.voice_provider,
        voice_id=settings.voice_id,
        voice_name=settings.voice_name,
        speaking_speed=settings.speaking_speed,  # type: ignore[arg-type]
        language=settings.language,
        ai_greeting=settings.ai_greeting,
        business_name=settings.business_name,
        assistant_name=settings.assistant_name,
        has_cartesia_api_key=bool(settings.cartesia_api_key_encrypted),
        cartesia_api_key_masked="********" if settings.cartesia_api_key_encrypted else "",
    )


def _phone_options(phone_numbers: list[TwilioPhoneNumber]) -> list[TwilioPhoneNumberOption]:
    return [
        TwilioPhoneNumberOption(
            phone_sid=number.phone_sid,
            phone_number=number.phone_number,
            friendly_name=number.friendly_name,
        )
        for number in phone_numbers
    ]


def _twilio_error_status(message: str) -> int:
    lowered = message.lower()
    if "unavailable" in lowered or "network" in lowered:
        return 503
    return 400
