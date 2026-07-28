"""Gmail OAuth connection routes for per-user outreach sending."""

from __future__ import annotations

import logging
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .auth import get_current_user
from .config import Settings, get_settings
from .database import get_db
from .gmail import GMAIL_SCOPES, GmailClient, GmailConfigurationError
from .gmail_connections import (
    disconnect_gmail_connection,
    get_gmail_connection,
    gmail_client_for_user,
    gmail_redirect_uri,
    upsert_gmail_connection,
)
from .models import GmailConnection, User
from .schemas import GmailConnectionStatus

router = APIRouter(prefix="/gmail", tags=["gmail"])
logger = logging.getLogger(__name__)

GMAIL_STATE_COOKIE = "leadforge_gmail_oauth_state"


@router.get("/status", response_model=GmailConnectionStatus)
def gmail_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GmailConnectionStatus:
    return _gmail_status(get_gmail_connection(db, current_user.id))


@router.get("/connect")
def connect_gmail(
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    if not settings.gmail_client_id or not settings.gmail_client_secret:
        raise HTTPException(status_code=503, detail="Gmail OAuth is not configured")

    state = secrets.token_urlsafe(32)
    params = {
        "client_id": settings.gmail_client_id,
        "redirect_uri": gmail_redirect_uri(settings),
        "response_type": "code",
        "scope": " ".join(GMAIL_SCOPES),
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    response = RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}")
    response.set_cookie(
        GMAIL_STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=settings.secure_auth_cookies,
        samesite="lax",
        domain=settings.auth_cookie_domain or None,
        path="/",
    )
    return response


@router.get("/callback")
def gmail_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    if error:
        logger.info("Gmail OAuth cancelled for user_id=%s: %s", current_user.id, error)
        return _settings_redirect(settings, "cancelled")
    if not code:
        logger.warning("Gmail OAuth callback missing code for user_id=%s", current_user.id)
        return _settings_redirect(settings, "error")

    redirect_uri = gmail_redirect_uri(settings)
    try:
        _validate_gmail_state(request, state)
        token_payload = _exchange_gmail_code(settings, code, redirect_uri)
        refresh_token = str(token_payload.get("refresh_token") or "")
        scopes = str(token_payload.get("scope") or " ".join(GMAIL_SCOPES))
        if not refresh_token:
            raise GmailConfigurationError(
                "Google did not return a Gmail refresh token. Reconnect Gmail and approve offline access."
            )
        gmail = GmailClient(settings.gmail_client_id, settings.gmail_client_secret, refresh_token)
        gmail.validate_configuration()
        upsert_gmail_connection(
            db,
            settings,
            user_id=current_user.id,
            gmail_email=gmail.profile_email,
            refresh_token=refresh_token,
            scopes=scopes,
        )
        db.commit()
        response = _settings_redirect(settings, "connected")
        response.delete_cookie(GMAIL_STATE_COOKIE, path="/", domain=settings.auth_cookie_domain or None)
        return response
    except HTTPException as exc:
        logger.warning("Gmail OAuth state validation failed for user_id=%s: %s", current_user.id, exc.detail)
        return _settings_redirect(settings, "error")
    except Exception as exc:
        db.rollback()
        logger.exception("Gmail OAuth callback failed for user_id=%s redirect_uri=%s", current_user.id, redirect_uri)
        return _settings_redirect(settings, "error")


@router.post("/check", response_model=GmailConnectionStatus)
def check_gmail_connection(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> GmailConnectionStatus:
    try:
        gmail_client_for_user(db, settings, current_user.id)
        connection = get_gmail_connection(db, current_user.id)
        db.commit()
        return _gmail_status(connection, health="ok")
    except Exception as exc:
        db.rollback()
        connection = get_gmail_connection(db, current_user.id)
        if connection:
            connection.last_error = str(exc)
            db.add(connection)
            db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/disconnect", response_model=GmailConnectionStatus)
def disconnect_gmail(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GmailConnectionStatus:
    connection = disconnect_gmail_connection(db, user_id=current_user.id)
    db.commit()
    return _gmail_status(connection)


def _exchange_gmail_code(settings: Settings, code: str, redirect_uri: str) -> dict[str, object]:
    if not settings.gmail_client_id or not settings.gmail_client_secret:
        raise GmailConfigurationError("Gmail OAuth is not configured")
    try:
        with httpx.Client(timeout=15) as client:
            response = client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.gmail_client_id,
                    "client_secret": settings.gmail_client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Gmail OAuth token exchange failed: status=%s redirect_uri=%s response=%s",
            exc.response.status_code,
            redirect_uri,
            exc.response.text[:500],
        )
        raise GmailConfigurationError("Gmail authorization failed. Check the Gmail OAuth client redirect URI.") from exc
    except httpx.RequestError as exc:
        logger.warning("Gmail OAuth token exchange request failed: %s", exc)
        raise GmailConfigurationError("Gmail authorization failed due to a network error.") from exc


def _validate_gmail_state(request: Request, state: str) -> None:
    expected = request.cookies.get(GMAIL_STATE_COOKIE, "")
    if not expected or not state or not secrets.compare_digest(expected, state):
        raise HTTPException(status_code=400, detail="Gmail OAuth state validation failed")


def _gmail_status(connection: GmailConnection | None, *, health: str | None = None) -> GmailConnectionStatus:
    if not connection:
        return GmailConnectionStatus(is_connected=False)
    current_health = health or ("connected" if connection.is_connected else "disconnected")
    if connection.last_error:
        current_health = "error"
    return GmailConnectionStatus(
        is_connected=connection.is_connected,
        gmail_email=connection.gmail_email,
        connected_at=connection.connected_at,
        disconnected_at=connection.disconnected_at,
        scopes=connection.scopes,
        health=current_health,
        last_health_check_at=connection.last_health_check_at,
        last_error=connection.last_error,
    )


def _settings_redirect(settings: Settings, status: str) -> RedirectResponse:
    return RedirectResponse(f"{settings.frontend_origin.rstrip('/')}/settings?gmail={status}")
