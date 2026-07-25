"""Authentication helpers for LeadForge SaaS accounts."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, Request, Response, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import get_db
from .models import RefreshToken, User

ACCESS_COOKIE = "leadforge_access"
REFRESH_COOKIE = "leadforge_refresh"
CSRF_COOKIE = "leadforge_csrf"
OAUTH_STATE_COOKIE = "leadforge_oauth_state"
OAUTH_NEXT_COOKIE = "leadforge_oauth_next"
ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    return pwd_context.verify(password, password_hash)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def is_admin_email(email: str, settings: Settings | None = None) -> bool:
    current_settings = settings or get_settings()
    return bool(current_settings.admin_email) and normalize_email(email) == current_settings.admin_email


def apply_admin_flag(user: User, settings: Settings | None = None) -> None:
    user.is_admin = is_admin_email(user.email, settings)


def create_access_token(user: User, settings: Settings | None = None) -> str:
    current_settings = settings or get_settings()
    now = utc_now()
    secret_key = current_settings.jwt_secret_key or "leadforge-development-secret"
    payload = {
        "sub": user.id,
        "email": normalize_email(user.email),
        "is_admin": user.is_admin,
        "type": "access",
        "iss": current_settings.jwt_issuer,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=current_settings.access_token_minutes),
    }
    return jwt.encode(payload, secret_key, algorithm=ALGORITHM)


def create_refresh_token(
    db: Session,
    user: User,
    request: Request,
    *,
    remember_me: bool,
    settings: Settings | None = None,
) -> tuple[str, RefreshToken]:
    current_settings = settings or get_settings()
    raw_token = secrets.token_urlsafe(64)
    days = current_settings.refresh_token_days if remember_me else current_settings.session_refresh_token_days
    record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        user_agent=(request.headers.get("user-agent") or "")[:500],
        ip_address=(request.client.host if request.client else "")[:80],
        expires_at=utc_now() + timedelta(days=days),
    )
    db.add(record)
    db.flush()
    return raw_token, record


def decode_access_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    current_settings = settings or get_settings()
    secret_key = current_settings.jwt_secret_key or "leadforge-development-secret"
    try:
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[ALGORITHM],
            issuer=current_settings.jwt_issuer,
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
        ) from exc
    if payload.get("type") != "access" or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")
    return payload


def extract_access_token(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return request.cookies.get(ACCESS_COOKIE, "")


def authenticate_request(
    request: Request,
    db: Session,
    settings: Settings | None = None,
) -> User:
    token = extract_access_token(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    payload = decode_access_token(token, settings)
    user = db.get(User, payload["sub"])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    apply_admin_flag(user, settings)
    request.state.current_user = user
    return user


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    existing = getattr(request.state, "current_user", None)
    if isinstance(existing, User):
        return existing
    return authenticate_request(request, db, settings)


def find_active_refresh_token(db: Session, raw_token: str) -> RefreshToken | None:
    if not raw_token:
        return None
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token)).limit(1))
    if not token or token.revoked_at or as_utc(token.expires_at) <= utc_now():
        return None
    return token


def revoke_refresh_token(db: Session, raw_token: str) -> None:
    token = find_active_refresh_token(db, raw_token)
    if token:
        token.revoked_at = utc_now()
        db.add(token)


def set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    remember_me: bool,
    settings: Settings | None = None,
) -> str:
    current_settings = settings or get_settings()
    csrf_token = secrets.token_urlsafe(32)
    domain = current_settings.auth_cookie_domain or None
    secure = current_settings.secure_auth_cookies
    access_max_age = current_settings.access_token_minutes * 60
    refresh_max_age = (
        current_settings.refresh_token_days
        if remember_me
        else current_settings.session_refresh_token_days
    ) * 24 * 60 * 60
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=access_max_age,
        httponly=True,
        secure=secure,
        samesite="lax",
        domain=domain,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=refresh_max_age,
        httponly=True,
        secure=secure,
        samesite="lax",
        domain=domain,
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=refresh_max_age,
        httponly=False,
        secure=secure,
        samesite="lax",
        domain=domain,
        path="/",
    )
    return csrf_token


def clear_auth_cookies(response: Response, settings: Settings | None = None) -> None:
    current_settings = settings or get_settings()
    domain = current_settings.auth_cookie_domain or None
    for name in (ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, domain=domain, path="/")
