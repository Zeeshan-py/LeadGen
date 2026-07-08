"""Gmail reply synchronization workflow.

This module polls Gmail threads for replies, stores received messages in CRM,
advances pipeline stages, and optionally sends a threaded auto-reply.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .config import Settings
from .gmail import GmailClient
from .models import Analytics, EmailMessage, Outreach
from .services.crm import change_crm_stage, mark_contacted, record_crm_activity
from .settings_store import effective_settings

logger = logging.getLogger(__name__)

ACTIVE_OUTREACH_STATUSES = ("sent", "opened", "replied", "closed")
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
    lead_id: str | None = None,
) -> ReplySyncResult:
    result = ReplySyncResult()
    query = (
        select(Outreach)
        .options(joinedload(Outreach.lead), joinedload(Outreach.campaign))
        .where(Outreach.status.in_(ACTIVE_OUTREACH_STATUSES))
    )
    if lead_id:
        query = query.where(Outreach.lead_id == lead_id)
    rows = db.scalars(query).all()
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
        try:
            thread_messages = gmail.thread_messages(outreach.gmail_thread_id)
        except Exception:
            result.failed += 1
            logger.exception("Gmail thread sync failed for outreach %s", outreach.id)
            continue

        sender_email = gmail.sender_email.strip().lower()
        lead_email = outreach.lead.email.strip().lower()
        new_inbound = []
        for message in thread_messages:
            existing = db.scalar(
                select(EmailMessage).where(
                    EmailMessage.gmail_message_id == message.gmail_message_id
                )
            )
            if existing:
                continue
            direction = "sent" if message.from_email == sender_email else "received"
            db.add(
                EmailMessage(
                    lead_id=outreach.lead_id,
                    outreach_id=outreach.id,
                    gmail_message_id=message.gmail_message_id,
                    gmail_thread_id=message.gmail_thread_id,
                    message_id_header=message.message_id_header,
                    direction=direction,
                    from_email=message.from_email,
                    to_email=message.to_email,
                    subject=message.subject,
                    body_text=message.body_text,
                    body_html=message.body_html,
                    snippet=message.snippet,
                    message_at=message.message_at,
                )
            )
            if direction == "received" and message.from_email == lead_email:
                new_inbound.append(message)

        if not new_inbound:
            db.commit()
            continue

        reply = new_inbound[-1]
        result.replied += 1
        now = datetime.now(timezone.utc)
        was_replied = outreach.replied_at is not None
        outreach.status = "replied"
        outreach.replied_at = now
        outreach.lead.outreach_status = "replied"
        mark_contacted(outreach.lead, reply.message_at)
        if outreach.lead.crm_stage not in {"won", "lost", "archived"}:
            change_crm_stage(
                db,
                outreach.lead,
                "replied",
                actor=reply.from_email or "Gmail",
            )
        if outreach.campaign and not was_replied:
            outreach.campaign.replies += 1
        db.add(
            Analytics(
                event_type="email_replied",
                lead_id=outreach.lead_id,
                campaign_id=outreach.campaign_id,
                metadata_json={"from": reply.from_email, "gmail_message_id": reply.gmail_message_id},
            )
        )
        record_crm_activity(
            db,
            lead_id=outreach.lead_id,
            event_type="reply_received",
            title="Reply received",
            description=reply.snippet or reply.body_text[:240],
            actor=reply.from_email or outreach.lead.contact_name or "Contact",
            metadata={
                "gmail_message_id": reply.gmail_message_id,
                "gmail_thread_id": outreach.gmail_thread_id,
            },
        )

        if effective.auto_reply_enabled and effective.auto_reply_body.strip():
            try:
                sent_reply = gmail.send_thread_reply(
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
                    EmailMessage(
                        lead_id=outreach.lead_id,
                        outreach_id=outreach.id,
                        gmail_message_id=sent_reply.message_id,
                        gmail_thread_id=sent_reply.thread_id,
                        direction="sent",
                        from_email=gmail.sender_email,
                        to_email=outreach.lead.email,
                        subject=outreach.subject_line,
                        body_text=effective.auto_reply_body.strip(),
                        snippet=effective.auto_reply_body.strip()[:240],
                        message_at=now,
                    )
                )
                db.add(
                    Analytics(
                        event_type="auto_reply_sent",
                        lead_id=outreach.lead_id,
                        campaign_id=outreach.campaign_id,
                        metadata_json={"gmail_thread_id": outreach.gmail_thread_id},
                    )
                )
                record_crm_activity(
                    db,
                    lead_id=outreach.lead_id,
                    event_type="auto_reply_sent",
                    title="Automatic reply sent",
                    description=effective.auto_reply_body.strip()[:240],
                    actor="LeadForge AI",
                    metadata={"gmail_thread_id": outreach.gmail_thread_id},
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
