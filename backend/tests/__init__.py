"""Backend regression tests."""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.orm import Session as OrmSession

TEST_USER_ID = "00000000-0000-0000-0000-000000000999"


def _assign_test_owner(session: OrmSession, _flush_context: object, _instances: object) -> None:
    for obj in session.new:
        if hasattr(obj, "user_id") and not getattr(obj, "user_id", None):
            setattr(obj, "user_id", TEST_USER_ID)


if not getattr(OrmSession, "_leadforge_test_owner_listener", False):
    event.listen(OrmSession, "before_flush", _assign_test_owner)
    setattr(OrmSession, "_leadforge_test_owner_listener", True)
