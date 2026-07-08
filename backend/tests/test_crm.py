"""Regression tests for CRM lead lifecycle and activity behavior."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.crm import _get_lead, _lead_detail, update_crm_lead
from app.database import Base
from app.gmail import _message_bodies
from app.models import CrmUser, EmailMessage, Lead, LeadNote
from app.schemas import CrmLeadUpdate
from app.services.crm import (
    change_crm_stage,
    record_crm_activity,
    replace_lead_tags,
)


class CrmTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def test_crm_profile_uses_relational_tags_notes_messages_and_activity(self) -> None:
        with Session(self.engine) as db:
            owner = CrmUser(
                name="Andy Manager",
                email="andy@example.test",
                initials="AM",
            )
            lead = Lead(
                dedupe_key="domain:greenfield.test",
                business_name="Greenfield Dental Care",
                contact_name="Michael Thompson",
                email="michael@greenfield.test",
                phone="+1 303 555 0198",
                location="123 Maple Street",
                country="United States",
                business_type="Healthcare",
                assigned_user=owner,
            )
            db.add_all([owner, lead])
            db.flush()
            replace_lead_tags(db, lead, ["Website", "Referral"])
            db.add(
                LeadNote(
                    lead_id=lead.id,
                    body="Prefers morning calls.",
                    created_by="Andy Manager",
                )
            )
            record_crm_activity(
                db,
                lead_id=lead.id,
                event_type="lead_generated",
                title="Lead generated",
            )
            change_crm_stage(db, lead, "interested", actor="Andy Manager")
            db.add(
                EmailMessage(
                    lead_id=lead.id,
                    gmail_message_id="gmail-message-1",
                    gmail_thread_id="gmail-thread-1",
                    direction="received",
                    from_email=lead.email,
                    to_email="sales@example.test",
                    subject="Re: Website ideas",
                    body_text="Let's schedule a call.",
                    snippet="Let's schedule a call.",
                    message_at=datetime.now(timezone.utc),
                )
            )
            db.commit()

            detail = _lead_detail(_get_lead(db, lead.id))

            self.assertEqual(detail.crm_stage, "interested")
            self.assertEqual(detail.assigned_user.name, "Andy Manager")
            self.assertEqual({tag.name for tag in detail.tags}, {"Website", "Referral"})
            self.assertEqual(detail.note_history[0].body, "Prefers morning calls.")
            self.assertEqual(detail.email_messages[0].gmail_thread_id, "gmail-thread-1")
            self.assertIn("Status changed to Interested", [item.title for item in detail.activity])

            updated = update_crm_lead(
                lead.id,
                CrmLeadUpdate(crm_stage="won"),
                db,
            )
            self.assertEqual(updated.crm_stage, "won")
            self.assertIn("Status changed to Won", [item.title for item in updated.activity])

    def test_gmail_multipart_body_is_decoded(self) -> None:
        text = base64.urlsafe_b64encode(b"Plain reply body").decode().rstrip("=")
        html = base64.urlsafe_b64encode(b"<p>Plain reply body</p>").decode().rstrip("=")

        body_text, body_html = _message_bodies(
            {
                "mimeType": "multipart/alternative",
                "parts": [
                    {"mimeType": "text/plain", "body": {"data": text}},
                    {"mimeType": "text/html", "body": {"data": html}},
                ],
            }
        )

        self.assertEqual(body_text, "Plain reply body")
        self.assertEqual(body_html, "<p>Plain reply body</p>")


if __name__ == "__main__":
    unittest.main()
