from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .config import Settings
from .gmail import GmailClient
from .models import Analytics, Outreach
from .settings_store import effective_settings

logger = logging.getLogger(__name__)

ACTIVE_OUTREACH_STATUSES = ("sent", "opened")
CLOSED_STATUS = "closed"


@dataclass
class ReplySyncResult:
    checked: int = 0
    replied: int = 0
    auto_replied: int = 0
    closed: int = 0
    failed: int = 0
    skipped: bool = False

    def to_dict(self) -> dict[str, int | bool]:
        return asdict(self)


def sync_replied_outreach(
    db: Session,
    settings: Settings,
    *,
    raise_on_missing_credentials: bool = True,
) -> ReplySyncResult:
    result = ReplySyncResult()
    rows = db.scalars(
        select(Outreach)
        .options(joinedload(Outreach.lead), joinedload(Outreach.campaign))
        .where(Outreach.status.in_(ACTIVE_OUTREACH_STATUSES))
    ).all()
    if not rows and not raise_on_missing_credentials:
        return result

    effective = effective_settings(settings, db)
    try:
        effective.require_gmail_credentials()
    except RuntimeError:
        if raise_on_missing_credentials:
            raise
        result.skipped = True
        return result

    try:
        gmail = GmailClient(
            effective.gmail_client_id,
            effective.gmail_client_secret,
            effective.gmail_refresh_token,
            effective.gmail_sender_email,
        )
    except Exception:
        if raise_on_missing_credentials:
            raise
        result.skipped = True
        return result
    for outreach in rows:
        result.checked += 1
        if not outreach.lead:
            continue
        reply = gmail.thread_reply_message(outreach.gmail_thread_id, gmail.sender_email, outreach.lead.email)
        if not reply:
            continue

        result.replied += 1
        now = datetime.now(timezone.utc)
        outreach.status = "replied"
        outreach.replied_at = now
        outreach.lead.outreach_status = "replied"
        if outreach.campaign:
            outreach.campaign.replies += 1
        db.add(
            Analytics(
                event_type="email_replied",
                lead_id=outreach.lead_id,
                campaign_id=outreach.campaign_id,
                metadata_json={"from": reply.from_email, "gmail_message_id": reply.gmail_message_id},
            )
        )

        if effective.auto_reply_enabled and effective.auto_reply_body.strip():
            try:
                gmail.send_thread_reply(
                    to_email=outreach.lead.email,
                    subject=outreach.subject_line,
                    body=effective.auto_reply_body.strip(),
                    thread_id=outreach.gmail_thread_id,
                    in_reply_to=reply.message_id_header,
                    references=reply.references_header,
                )
                result.auto_replied += 1
                outreach.status = CLOSED_STATUS
                outreach.lead.outreach_status = CLOSED_STATUS
                outreach.lead.lead_status = CLOSED_STATUS
                result.closed += 1
                db.add(
                    Analytics(
                        event_type="auto_reply_sent",
                        lead_id=outreach.lead_id,
                        campaign_id=outreach.campaign_id,
                        metadata_json={"gmail_thread_id": outreach.gmail_thread_id},
                    )
                )
                db.add(
                    Analytics(
                        event_type="client_closed",
                        lead_id=outreach.lead_id,
                        campaign_id=outreach.campaign_id,
                        metadata_json={"reason": "client_replied"},
                    )
                )
            except Exception as exc:
                result.failed += 1
                outreach.failed_reason = f"Auto reply failed: {exc}"
                logger.exception("Auto reply failed for outreach %s", outreach.id)

    db.commit()
    return result
