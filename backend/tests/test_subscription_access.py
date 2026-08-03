"""Regression tests for plan entitlements and usage limits."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Lead, Outreach, PaddleSubscription, User
from app.subscription_access import (
    assert_generate_leads_allowed,
    assert_outreach_send_allowed,
    require_feature,
    subscription_access_payload,
)


class SubscriptionAccessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def test_free_plan_has_basic_lead_generation_only(self) -> None:
        with Session(self.engine) as db:
            user = User(email="free@example.test", full_name="Free User")
            db.add(user)
            db.commit()
            db.refresh(user)

            access = subscription_access_payload(db, user)

        self.assertEqual(access["plan_key"], "free")
        self.assertEqual(access["lead_limit"], 10)
        self.assertTrue(access["features"]["lead_generation"])
        self.assertFalse(access["features"]["crm"])
        self.assertFalse(access["features"]["csv_export"])

    def test_free_plan_monthly_lead_limit_blocks_generation(self) -> None:
        with Session(self.engine) as db:
            user = User(email="limit@example.test", full_name="Limit User")
            db.add(user)
            db.commit()
            db.refresh(user)
            for index in range(10):
                db.add(
                    Lead(
                        user_id=user.id,
                        dedupe_key=f"lead-{index}",
                        business_name=f"Lead {index}",
                        created_at=datetime.now(timezone.utc),
                    )
                )
            db.commit()

            with self.assertRaises(HTTPException) as raised:
                assert_generate_leads_allowed(
                    db,
                    user,
                    requested_count=1,
                    website_mode="withWebsite",
                    campaign_name=None,
                )

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.detail["code"], "limit_reached")
        self.assertEqual(raised.exception.detail["usage"]["limit"], 10)

    def test_basic_plan_allows_crm_and_limits_daily_outreach(self) -> None:
        with Session(self.engine) as db:
            user = User(email="basic@example.test", full_name="Basic User")
            db.add(user)
            db.commit()
            db.refresh(user)
            db.add(
                PaddleSubscription(
                    subscription_id="sub_basic",
                    user_id=user.id,
                    customer_id="ctm_basic",
                    status="active",
                    plan_key="basic",
                    current_period_ends_at=datetime.now(timezone.utc) + timedelta(days=20),
                )
            )
            lead = Lead(user_id=user.id, dedupe_key="basic-lead", business_name="Basic Lead")
            db.add(lead)
            db.commit()
            db.refresh(lead)
            for index in range(7):
                db.add(
                    Outreach(
                        user_id=user.id,
                        lead_id=lead.id,
                        subject_line=f"Subject {index}",
                        sent_at=datetime.now(timezone.utc),
                    )
                )
            db.commit()

            require_feature(db, user, "crm")
            with self.assertRaises(HTTPException) as raised:
                require_feature(db, user, "campaigns")
            with self.assertRaises(HTTPException) as limit_raised:
                assert_outreach_send_allowed(db, user)

        self.assertEqual(raised.exception.detail["required_plan"], "agent")
        self.assertEqual(limit_raised.exception.detail["code"], "limit_reached")
        self.assertEqual(limit_raised.exception.detail["usage"]["limit"], 7)

    def test_agency_plan_unlocks_ai_sdr_and_reply_sync(self) -> None:
        with Session(self.engine) as db:
            user = User(email="agency@example.test", full_name="Agency User")
            db.add(user)
            db.commit()
            db.refresh(user)
            db.add(
                PaddleSubscription(
                    subscription_id="sub_agency",
                    user_id=user.id,
                    customer_id="ctm_agency",
                    status="active",
                    plan_key="agency",
                    current_period_ends_at=datetime.now(timezone.utc) + timedelta(days=20),
                )
            )
            db.commit()

            access = subscription_access_payload(db, user)
            require_feature(db, user, "ai_sdr")
            require_feature(db, user, "reply_sync")

        self.assertTrue(access["features"]["ai_sdr"])
        self.assertTrue(access["features"]["reply_sync"])
        self.assertIsNone(access["outreach_daily_limit"])

    def test_admin_user_unlocks_all_features_without_subscription(self) -> None:
        with Session(self.engine) as db:
            user = User(email="admin@example.test", full_name="Admin User", is_admin=True)
            db.add(user)
            db.commit()
            db.refresh(user)

            access = subscription_access_payload(db, user)
            require_feature(db, user, "crm")
            require_feature(db, user, "analytics")
            require_feature(db, user, "campaigns")
            require_feature(db, user, "ai_sdr")
            assert_generate_leads_allowed(
                db,
                user,
                requested_count=5000,
                website_mode="allPlaces",
                campaign_name="Admin campaign",
            )
            assert_outreach_send_allowed(db, user)

        self.assertEqual(access["plan_key"], "agency")
        self.assertEqual(access["plan_name"], "Admin")
        self.assertEqual(access["status"], "admin")
        self.assertTrue(all(access["features"].values()))
        self.assertIsNone(access["outreach_daily_limit"])


if __name__ == "__main__":
    unittest.main()
