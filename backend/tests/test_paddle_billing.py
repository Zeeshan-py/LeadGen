"""Regression tests for Paddle Billing webhook sync."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import time
import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import Base
from app.models import PaddleSubscription, User
from app.paddle_billing import (
    _PADDLE_IP_CACHE,
    PaddleWebhookSourceError,
    billing_plans,
    billing_plans_response,
    create_checkout_payload,
    process_paddle_webhook,
    verify_paddle_signature,
    verify_paddle_webhook_source_ip,
)
from app.paddle_routes import paddle_webhook_status


class PaddleBillingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.settings = Settings(
            _env_file=None,
            PADDLE_ENV="sandbox",
            PADDLE_SANDBOX_API_KEY="pdl_sdbx_test",
            PADDLE_SANDBOX_CLIENT_TOKEN="test_client_token",
            PADDLE_WEBHOOK_SECRET="ntfsec_test",
            PADDLE_BASIC_PRODUCT_ID="pro_basic_test",
            PADDLE_BASIC_PRICE_ID="pri_basic_test",
            PADDLE_AGENT_PRODUCT_ID="pro_agent_test",
            PADDLE_AGENT_PRICE_ID="pri_agent_test",
            PADDLE_AGENCY_PRODUCT_ID="pro_agency_test",
            PADDLE_AGENCY_PRICE_ID="pri_agency_test",
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
                            "id": self.settings.paddle_agent_price_id,
                            "product_id": self.settings.paddle_agent_product_id,
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
        self.assertEqual(subscription.price_id, self.settings.paddle_agent_price_id)

    def test_checkout_payload_uses_authenticated_user_and_current_plan(self) -> None:
        user_id = "00000000-0000-0000-0000-000000000022"
        with Session(self.engine) as db:
            user = User(id=user_id, email="buyer@example.test", full_name="Buyer")
            db.add(user)
            db.add(
                PaddleSubscription(
                    subscription_id="sub_current",
                    user_id=user_id,
                    customer_id="ctm_current",
                    status="active",
                    plan_key="basic",
                    price_id=self.settings.paddle_basic_price_id,
                    product_id=self.settings.paddle_basic_product_id,
                )
            )
            db.commit()

            payload = create_checkout_payload(db, user, self.settings, "agency")

        self.assertEqual(payload.client_token, "test_client_token")
        self.assertEqual(payload.plan_key, "agency")
        self.assertEqual(payload.price_id, self.settings.paddle_agency_price_id)
        self.assertEqual(payload.custom_data["leadforge_user_id"], user_id)
        self.assertEqual(payload.custom_data["email"], "buyer@example.test")
        self.assertEqual(payload.custom_data["current_plan"], "basic")

    def test_billing_plan_copy_matches_lead_quotas(self) -> None:
        plans = {plan.key: plan for plan in billing_plans(self.settings)}

        self.assertIn("400 leads per month", plans["basic"].features)
        self.assertIn("800 leads per month", plans["agent"].features)
        self.assertIn("1,500 leads per month", plans["agency"].features)

    def test_billing_plans_response_exposes_public_client_token(self) -> None:
        payload = billing_plans_response(self.settings)

        self.assertEqual(payload.client_token, "test_client_token")
        self.assertTrue(payload.client_token_configured)
        self.assertTrue(payload.checkout_ready)

    def test_webhook_get_reports_endpoint_status(self) -> None:
        payload = paddle_webhook_status()

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["method"], "POST")
        self.assertIn("signed POST", payload["message"])


class PaddleWebhookIpAllowlistTests(unittest.IsolatedAsyncioTestCase):
    async def test_live_production_requires_paddle_source_ip(self) -> None:
        settings = Settings(_env_file=None, environment="production", PADDLE_ENV="production")
        _PADDLE_IP_CACHE[settings.paddle_ips_url] = (
            time.time(),
            [ipaddress.ip_network("34.194.127.46/32")],
        )
        try:
            await verify_paddle_webhook_source_ip(settings, "34.194.127.46")
            with self.assertRaises(PaddleWebhookSourceError):
                await verify_paddle_webhook_source_ip(settings, "203.0.113.10")
        finally:
            _PADDLE_IP_CACHE.pop(settings.paddle_ips_url, None)

    async def test_sandbox_does_not_require_paddle_source_ip(self) -> None:
        settings = Settings(_env_file=None, environment="production", PADDLE_ENV="sandbox")

        await verify_paddle_webhook_source_ip(settings, "203.0.113.10")


if __name__ == "__main__":
    unittest.main()
