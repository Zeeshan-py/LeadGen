"""Authentication API routes for private LeadForge workspaces."""

from __future__ import annotations

import re
import secrets
import threading
import logging
from datetime import timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .auth import (
    OAUTH_NEXT_COOKIE,
    OAUTH_STATE_COOKIE,
    as_utc,
    apply_admin_flag,
    clear_auth_cookies,
    create_access_token,
    create_refresh_token,
    find_active_refresh_token,
    get_current_user,
    hash_password,
    hash_token,
    is_admin_email,
    normalize_email,
    revoke_refresh_token,
    set_auth_cookies,
    utc_now,
    verify_password,
)
from .config import Settings, get_settings
from .database import get_db
from .disposable_email import DisposableEmailRejected, ensure_signup_email_allowed
from .models import PasswordResetToken, User

router = APIRouter(prefix="/auth", tags=["auth"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_MIN_LENGTH = 8
MAX_USER_AVATAR_URL_LENGTH = 800

logger = logging.getLogger("leadforge.auth")

_rate_lock = threading.Lock()
_rate_events: dict[str, list[float]] = {}


class UserRead(BaseModel):
    id: str
    full_name: str
    email: str
    provider: str
    avatar_url: str
    is_admin: bool
    is_verified: bool
    created_at: str
    last_login: str | None


class AuthResponse(BaseModel):
    user: UserRead
    csrf_token: str


class SignUpRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=128)
    remember_me: bool = False

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        email = normalize_email(value)
        if not EMAIL_RE.match(email):
            raise ValueError("Enter a valid email address")
        return email

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return " ".join(value.strip().split())


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)
    remember_me: bool = False

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        email = normalize_email(value)
        if not EMAIL_RE.match(email):
            raise ValueError("Enter a valid email address")
        return email


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        return normalize_email(value)


class ForgotPasswordResponse(BaseModel):
    message: str
    reset_token: str | None = None
    reset_url: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=128)


@router.post("/signup", response_model=AuthResponse)
def signup(
    payload: SignUpRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    _rate_limit(_rate_key(request, "signup", payload.email), limit=10, window_seconds=60 * 60)
    if is_admin_email(payload.email, settings):
        raise HTTPException(status_code=400, detail="Use the configured admin login for this email address")
    try:
        ensure_signup_email_allowed(payload.email, settings)
    except DisposableEmailRejected as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    existing = db.scalar(select(User).where(User.email == payload.email).limit(1))
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(
        full_name=payload.full_name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        provider="email",
        provider_id="",
        is_verified=True,
    )
    apply_admin_flag(user, settings)
    db.add(user)
    db.flush()
    return _issue_session(db, user, request, response, payload.remember_me, settings)


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    _rate_limit(_rate_key(request, "login", payload.email), limit=8, window_seconds=15 * 60)
    user = db.scalar(select(User).where(User.email == payload.email).limit(1))

    if is_admin_email(payload.email, settings):
        if not settings.admin_password or not secrets.compare_digest(payload.password, settings.admin_password):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        user = user or User(full_name="LeadForge Admin", email=payload.email, provider="email", is_verified=True)
        user.password_hash = user.password_hash or ""
        user.provider = user.provider or "email"
        user.is_verified = True
        apply_admin_flag(user, settings)
        db.add(user)
        db.flush()
        return _issue_session(db, user, request, response, payload.remember_me, settings)

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    apply_admin_flag(user, settings)
    return _issue_session(db, user, request, response, payload.remember_me, settings)


@router.post("/refresh", response_model=AuthResponse)
def refresh_session(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    raw_refresh = request.cookies.get("leadforge_refresh", "")
    token = find_active_refresh_token(db, raw_refresh)
    if not token:
        clear_auth_cookies(response, settings)
        raise HTTPException(status_code=401, detail="Session expired")
    user = db.get(User, token.user_id)
    if not user:
        clear_auth_cookies(response, settings)
        raise HTTPException(status_code=401, detail="Session expired")
    token.revoked_at = utc_now()
    db.add(token)
    apply_admin_flag(user, settings)
    return _issue_session(db, user, request, response, remember_me=True, settings=settings)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    revoke_refresh_token(db, request.cookies.get("leadforge_refresh", ""))
    db.commit()
    clear_auth_cookies(response, settings)
    return {"status": "logged_out"}


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return _user_read(current_user)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ForgotPasswordResponse:
    email = normalize_email(payload.email)
    _rate_limit(_rate_key(request, "forgot", email), limit=5, window_seconds=15 * 60)
    user = db.scalar(select(User).where(User.email == email).limit(1))
    reset_token_value: str | None = None
    if user:
        raw_token = secrets.token_urlsafe(48)
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=utc_now() + timedelta(minutes=settings.password_reset_token_minutes),
        )
        db.add(reset_token)
        db.commit()
        if settings.environment.lower() != "production":
            reset_token_value = raw_token

    message = "If an account exists for that email, a password reset link has been prepared."
    if reset_token_value:
        reset_url = f"{settings.frontend_origin.rstrip('/')}/reset-password?token={reset_token_value}"
        return ForgotPasswordResponse(message=message, reset_token=reset_token_value, reset_url=reset_url)
    return ForgotPasswordResponse(message=message)


@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    token = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == hash_token(payload.token))
        .limit(1)
    )
    if not token or token.used_at or as_utc(token.expires_at) <= utc_now():
        raise HTTPException(status_code=400, detail="Reset link is invalid or expired")
    user = db.get(User, token.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Reset link is invalid or expired")
    user.password_hash = hash_password(payload.password)
    user.provider = user.provider or "email"
    user.is_verified = True
    token.used_at = utc_now()
    db.add_all([user, token])
    db.commit()
    return {"status": "password_reset"}


@router.get("/google/login")
def google_login(
    request: Request,
    next: str = Query(default="/dashboard"),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": settings.oauth_redirect_uri("google"),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    response = RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}")
    _set_oauth_cookies(response, state, _safe_next(next), settings)
    return response


@router.get("/google/callback")
def google_callback(
    request: Request,
    code: str = "",
    state: str = "",
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        logger.error("Google OAuth callback received while Google OAuth is not configured")
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")
    if not code:
        logger.warning("Google OAuth callback missing authorization code")
        raise HTTPException(status_code=400, detail="Google authentication was cancelled or failed")

    _validate_oauth_state(request, state)
    redirect_uri = settings.oauth_redirect_uri("google")
    try:
        with httpx.Client(timeout=15) as client:
            token_response = client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.google_oauth_client_id,
                    "client_secret": settings.google_oauth_client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_response.raise_for_status()
            access_token = token_response.json().get("access_token")
            if not access_token:
                logger.error("Google OAuth token response did not include an access token")
                raise HTTPException(status_code=502, detail="Google authentication failed")

            user_response = client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_response.raise_for_status()
            profile = user_response.json()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Google OAuth provider request failed: status=%s endpoint=%s redirect_uri=%s response=%s",
            exc.response.status_code,
            exc.request.url,
            redirect_uri,
            exc.response.text[:500],
        )
        raise HTTPException(status_code=502, detail="Google authentication failed") from exc
    except httpx.RequestError as exc:
        logger.warning("Google OAuth provider request error: endpoint=%s error=%s", exc.request.url, exc)
        raise HTTPException(status_code=502, detail="Google authentication failed") from exc

    try:
        user = _upsert_oauth_user(
            db,
            provider="google",
            provider_id=str(profile.get("sub") or ""),
            email=str(profile.get("email") or ""),
            full_name=str(profile.get("name") or ""),
            avatar_url=str(profile.get("picture") or ""),
            is_verified=bool(profile.get("email_verified")),
            settings=settings,
        )
        return _oauth_session_redirect(db, user, request, settings)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Google OAuth user persistence failed")
        raise HTTPException(status_code=500, detail="Could not complete Google login") from exc


@router.get("/github/login")
def github_login(
    request: Request,
    next: str = Query(default="/dashboard"),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    if not settings.github_oauth_client_id or not settings.github_oauth_client_secret:
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured")
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": settings.github_oauth_client_id,
        "redirect_uri": settings.oauth_redirect_uri("github"),
        "scope": "read:user user:email",
        "state": state,
        "allow_signup": "true",
    }
    response = RedirectResponse(f"https://github.com/login/oauth/authorize?{urlencode(params)}")
    _set_oauth_cookies(response, state, _safe_next(next), settings)
    return response


@router.get("/github/callback")
def github_callback(
    request: Request,
    code: str = "",
    state: str = "",
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    _validate_oauth_state(request, state)
    with httpx.Client(timeout=15, headers={"Accept": "application/json"}) as client:
        token_response = client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "code": code,
                "client_id": settings.github_oauth_client_id,
                "client_secret": settings.github_oauth_client_secret,
                "redirect_uri": settings.oauth_redirect_uri("github"),
            },
        )
        token_response.raise_for_status()
        access_token = token_response.json().get("access_token")
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"}
        profile_response = client.get("https://api.github.com/user", headers=headers)
        profile_response.raise_for_status()
        profile = profile_response.json()
        emails_response = client.get("https://api.github.com/user/emails", headers=headers)
        emails_response.raise_for_status()
        emails = emails_response.json()
    email = _github_primary_email(emails) or str(profile.get("email") or "")
    user = _upsert_oauth_user(
        db,
        provider="github",
        provider_id=str(profile.get("id") or ""),
        email=email,
        full_name=str(profile.get("name") or profile.get("login") or ""),
        avatar_url=str(profile.get("avatar_url") or ""),
        is_verified=bool(email),
        settings=settings,
    )
    return _oauth_session_redirect(db, user, request, settings)


def _issue_session(
    db: Session,
    user: User,
    request: Request,
    response: Response,
    remember_me: bool,
    settings: Settings,
) -> AuthResponse:
    user.email = normalize_email(user.email)
    apply_admin_flag(user, settings)
    user.last_login = utc_now()
    db.add(user)
    db.flush()
    access_token = create_access_token(user, settings)
    refresh_token, _ = create_refresh_token(db, user, request, remember_me=remember_me, settings=settings)
    csrf_token = set_auth_cookies(
        response,
        access_token=access_token,
        refresh_token=refresh_token,
        remember_me=remember_me,
        settings=settings,
    )
    db.commit()
    db.refresh(user)
    return AuthResponse(user=_user_read(user), csrf_token=csrf_token)


def _user_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        provider=user.provider,
        avatar_url=user.avatar_url,
        is_admin=user.is_admin,
        is_verified=user.is_verified,
        created_at=user.created_at.isoformat(),
        last_login=user.last_login.isoformat() if user.last_login else None,
    )


def _upsert_oauth_user(
    db: Session,
    *,
    provider: str,
    provider_id: str,
    email: str,
    full_name: str,
    avatar_url: str,
    is_verified: bool,
    settings: Settings,
) -> User:
    clean_email = normalize_email(email)
    if not clean_email or not EMAIL_RE.match(clean_email):
        raise HTTPException(status_code=400, detail=f"{provider.title()} did not return a usable email address")
    user = db.scalar(
        select(User)
        .where(User.provider == provider, User.provider_id == provider_id)
        .limit(1)
    )
    user = user or db.scalar(select(User).where(User.email == clean_email).limit(1))
    if not user:
        user = User(email=clean_email)
    user.full_name = full_name.strip() or user.full_name or clean_email.split("@", 1)[0]
    user.provider = provider
    user.provider_id = provider_id
    user.avatar_url = _safe_avatar_url(avatar_url)
    user.is_verified = is_verified
    apply_admin_flag(user, settings)
    db.add(user)
    db.flush()
    return user


def _oauth_session_redirect(
    db: Session,
    user: User,
    request: Request,
    settings: Settings,
) -> RedirectResponse:
    next_path = _safe_next(request.cookies.get(OAUTH_NEXT_COOKIE, "/dashboard"))
    response = RedirectResponse(f"{settings.frontend_origin.rstrip('/')}{next_path}")
    _issue_session(db, user, request, response, remember_me=True, settings=settings)
    response.delete_cookie(OAUTH_STATE_COOKIE, path="/")
    response.delete_cookie(OAUTH_NEXT_COOKIE, path="/")
    return response


def _set_oauth_cookies(response: Response, state: str, next_path: str, settings: Settings) -> None:
    secure = settings.secure_auth_cookies
    domain = settings.auth_cookie_domain or None
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=secure,
        samesite="lax",
        domain=domain,
        path="/",
    )
    response.set_cookie(
        OAUTH_NEXT_COOKIE,
        next_path,
        max_age=600,
        httponly=True,
        secure=secure,
        samesite="lax",
        domain=domain,
        path="/",
    )


def _validate_oauth_state(request: Request, state: str) -> None:
    expected = request.cookies.get(OAUTH_STATE_COOKIE, "")
    if not expected or not state or not secrets.compare_digest(expected, state):
        raise HTTPException(status_code=400, detail="OAuth state validation failed")


def _safe_next(value: str) -> str:
    candidate = value.strip() or "/dashboard"
    if not candidate.startswith("/") or candidate.startswith("//") or "://" in candidate:
        return "/dashboard"
    return candidate


def _safe_avatar_url(value: str) -> str:
    avatar_url = value.strip()
    if len(avatar_url) <= MAX_USER_AVATAR_URL_LENGTH:
        return avatar_url
    logger.info(
        "OAuth avatar URL exceeded storage limit and was omitted: length=%s max=%s",
        len(avatar_url),
        MAX_USER_AVATAR_URL_LENGTH,
    )
    return ""


def _github_primary_email(rows: Any) -> str:
    if not isinstance(rows, list):
        return ""
    verified = [
        row
        for row in rows
        if isinstance(row, dict) and row.get("email") and row.get("verified")
    ]
    primary = next((row for row in verified if row.get("primary")), None)
    selected = primary or (verified[0] if verified else None)
    return normalize_email(str(selected.get("email") or "")) if selected else ""


def _rate_key(request: Request, action: str, email: str) -> str:
    ip = request.client.host if request.client else "unknown"
    return f"{action}:{ip}:{normalize_email(email)}"


def _rate_limit(key: str, *, limit: int, window_seconds: int) -> None:
    now = utc_now().timestamp()
    floor = now - window_seconds
    with _rate_lock:
        events = [stamp for stamp in _rate_events.get(key, []) if stamp >= floor]
        if len(events) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Please wait and try again.",
            )
        events.append(now)
        _rate_events[key] = events
