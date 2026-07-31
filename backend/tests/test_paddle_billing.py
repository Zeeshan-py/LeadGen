"""Regression tests for Paddle Billing webhook sync."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import Base
from app.models import PaddleSubscription, User
from app.paddle_billing import process_paddle_webhook, verify_paddle_signature


class PaddleBillingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.settings = Settings(
            _env_file=None,
            PADDLE_ENV="sandbox",
            PADDLE_SANDBOX_API_KEY="pdl_sdbx_test",
            PADDLE_WEBHOOK_SECRET="ntfsec_test",
        )

    def test_signature_verification_accepts_valid_paddle_header(self) -> None:
        raw_body = b'{"event_id":"evt_test","event_type":"subscription.created","data":{}}'
        timestamp = str(int(time.time()))
        digest = hmac.new(
            self.settings.paddle_webhook_secret.encode("utf-8"),
            f"{timestamp}:{raw_body.decode('utf-8')}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        verify_paddle_signature(
            raw_body,
            f"ts={timestamp};h1={digest}",
            self.settings.paddle_webhook_secret,
            tolerance_seconds=300,
        )

    def test_subscription_webhook_links_user_and_is_idempotent(self) -> None:
        user_id = "00000000-0000-0000-0000-000000000011"
        event = {
            "event_id": "evt_subscription_created",
            "event_type": "subscription.created",
            "occurred_at": "2026-07-31T00:00:00Z",
            "data": {
                "id": "sub_01kys4testsubscription000000",
                "customer_id": "ctm_01kys4testcustomer0000000",
                "status": "active",
                "currency_code": "USD",
                "billing_cycle": {"interval": "month", "frequency": 1},
                "current_billing_period": {
                    "starts_at": "2026-07-31T00:00:00Z",
                    "ends_at": "2026-08-31T00:00:00Z",
                },
                "items": [
                    {
                        "quantity": 1,
                        "price": {
                            "id": self.settings.paddle_price_agent_monthly,
                            "product_id": "pro_01kys3xzth1mn7gwrq6k0rd0p8",
                        },
                    }
                ],
                "custom_data": {"leadforge_user_id": user_id},
            },
        }

        with Session(self.engine) as db:
            db.add(User(id=user_id, email="buyer@example.test", full_name="Buyer"))
            db.commit()

            first = process_paddle_webhook(db, event, self.settings)
            second = process_paddle_webhook(db, event, self.settings)
            subscription = db.scalar(select(PaddleSubscription).limit(1))

        self.assertEqual(first["status"], "processed")
        self.assertEqual(second["status"], "duplicate")
        self.assertIsNotNone(subscription)
        assert subscription is not None
        self.assertEqual(subscription.user_id, user_id)
        self.assertEqual(subscription.plan_key, "agent")
        self.assertEqual(subscription.price_id, self.settings.paddle_price_agent_monthly)


if __name__ == "__main__":
    unittest.main()
