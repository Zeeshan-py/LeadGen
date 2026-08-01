"""Small in-process rate limiting helpers for public and authenticated APIs."""

from __future__ import annotations

import threading
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from .auth import utc_now

_lock = threading.Lock()
_events: dict[str, deque[float]] = defaultdict(deque)


def client_ip(request: Request | None) -> str:
    """Return the best available client IP behind Railway/uvicorn proxy headers."""
    if request is None:
        return "test-client"
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()[:80] or "unknown"
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip[:80]
    return (request.client.host if request.client else "unknown")[:80]


def rate_limit_key(request: Request | None, action: str, subject: str = "") -> str:
    clean_subject = subject.strip().lower()[:320]
    return f"{action}:{client_ip(request)}:{clean_subject}"


def enforce_rate_limit(
    key: str,
    *,
    limit: int,
    window_seconds: int,
    message: str = "Too many attempts. Please wait and try again.",
) -> None:
    now = utc_now().timestamp()
    floor = now - window_seconds
    with _lock:
        events = _events[key]
        while events and events[0] < floor:
            events.popleft()
        if len(events) >= limit:
            retry_after = max(1, int(window_seconds - (now - events[0]))) if events else window_seconds
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=message,
                headers={"Retry-After": str(retry_after)},
            )
        events.append(now)


def clear_rate_limits_for_tests() -> None:
    with _lock:
        _events.clear()
