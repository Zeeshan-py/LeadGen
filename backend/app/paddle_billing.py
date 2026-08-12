"""Paddle Billing integration for LeadForge subscriptions.

The frontend opens Paddle Checkout with a client-side token. The backend keeps
server API calls, webhook verification, subscription state, and customer portal
links isolated from the public runtime.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from .auth import as_utc, normalize_email, utc_now
from .config import Settings
from .models import PaddleCustomer, PaddleSubscription, PaddleTransaction, PaddleWebhookEvent, User
from .schemas import (
    BillingOverview,
    BillingPlan,
    BillingPlansResponse,
    PaddleCheckoutSession,
    PaddleCustomerRead,
    PaddleSubscriptionRead,
    PaddleTransactionRead,
)

logger = logging.getLogger(__name__)


class PaddleConfigurationError(RuntimeError):
    """Raised when required Paddle environment variables are missing."""


class PaddleAPIError(RuntimeError):
    """Raised when Paddle returns a failed API response."""


def billing_plans(settings: Settings) -> list[BillingPlan]:
    return [
        BillingPlan(
            key="basic",
            name="Basic",
            description="For solo operators validating a focused outbound workflow.",
            price_id=settings.paddle_basic_price_id,
            product_id=settings.paddle_basic_product_id,
            amount="1500",
            currency_code="USD",
            interval="month",
            configured=bool(settings.paddle_basic_price_id and settings.paddle_basic_product_id),
            features=[
                "400 leads per month",
                "Lead generation workspace",
                "CRM pipeline",
                "Gmail outreach connection",
                "Outreach up to 7 emails per day",
                "Analytics dashboard",
                "CSV export",
            ],
        ),
        BillingPlan(
            key="agent",
            name="Agent",
            description="For growing teams running AI-assisted prospecting and outreach.",
            price_id=settings.paddle_agent_price_id,
            product_id=settings.paddle_agent_product_id,
            amount="3000",
            currency_code="USD",
            interval="month",
            highlighted=True,
            configured=bool(settings.paddle_agent_price_id and settings.paddle_agent_product_id),
            features=[
                "800 leads per month",
                "Everything in Basic",
                "Campaign management",
                "Advanced filters",
                "Outreach up to 20 emails per day",
                "Full CRM and analytics",
            ],
        ),
        BillingPlan(
            key="agency",
            name="Agency",
            description="For agencies managing higher-volume client acquisition workflows.",
            price_id=settings.paddle_agency_price_id,
            product_id=settings.paddle_agency_product_id,
            amount="5000",
            currency_code="USD",
            interval="month",
            configured=bool(settings.paddle_agency_price_id and settings.paddle_agency_product_id),
            features=[
                "1,500 leads per month",
                "Everything in Agent",
                "AI SDR workspace",
                "Twilio calling and voice settings",
                "Campaign automation",
                "Unlimited outreach",
                "Reply sync",
                "Agency-ready reporting",
            ],
        ),
    ]


def billing_plans_response(settings: Settings) -> BillingPlansResponse:
    plans = billing_plans(settings)
    return BillingPlansResponse(
        environment="sandbox" if settings.paddle_is_sandbox else "production",
        client_token_configured=bool(settings.paddle_client_token),
        checkout_ready=bool(settings.paddle_client_token) and all(plan.configured for plan in plans),
        plans=plans,
    )


def find_plan_by_price_id(settings: Settings, price_id: str) -> BillingPlan | None:
    return next((plan for plan in billing_plans(settings) if plan.price_id == price_id), None)


def find_plan_by_key(settings: Settings, plan_key: str) -> BillingPlan | None:
    return next((plan for plan in billing_plans(settings) if plan.key == plan_key), None)


def create_checkout_payload(db: Session, user: User, settings: Settings, plan_key: str) -> PaddleCheckoutSession:
    plan = find_plan_by_key(settings, plan_key)
    if not plan:
        raise PaddleConfigurationError("Unknown LeadForge billing plan")
    if not plan.configured:
        raise PaddleConfigurationError(
            f"Paddle catalog variables for the {plan.name} plan are not fully configured"
        )
    if not settings.paddle_client_token:
        missing = "PADDLE_SANDBOX_CLIENT_TOKEN" if settings.paddle_is_sandbox else "PADDLE_LIVE_CLIENT_TOKEN"
        raise PaddleConfigurationError(f"{missing} is not configured")

    subscription = get_primary_subscription_for_user(db, user.id)
    current_plan = subscription_access_plan(subscription) if subscription else "none"
    customer = get_customer_for_user(db, user.id)

    return PaddleCheckoutSession(
        environment="sandbox" if settings.paddle_is_sandbox else "production",
        client_token=settings.paddle_client_token,
        plan_key=plan.key,
        plan_name=plan.name,
        price_id=plan.price_id,
        product_id=plan.product_id,
        quantity=1,
        customer={
            "email": user.email,
            "paddle_customer_id": customer.customer_id if customer else "",
        },
        custom_data={
            "leadforge_user_id": user.id,
            "user_id": user.id,
            "email": user.email,
            "current_plan": current_plan,
            "current_plan_key": current_plan,
            "target_plan": plan.key,
            "plan_key": plan.key,
            "source": "leadforge_billing_checkout",
        },
        success_url=_absolute_frontend_url(settings, settings.paddle_success_url or "/billing/success"),
        cancel_url=_absolute_frontend_url(settings, settings.paddle_cancel_url or "/billing/cancel"),
    )


async def paddle_api_request(
    settings: Settings,
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    if not settings.paddle_api_key:
        missing = "PADDLE_SANDBOX_API_KEY" if settings.paddle_is_sandbox else "PADDLE_LIVE_API_KEY"
        raise PaddleConfigurationError(f"{missing} is not configured")

    url = f"{settings.paddle_api_base_url.rstrip('/')}/{path.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {settings.paddle_api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.request(method, url, headers=headers, json=json_body, params=params)

    if response.status_code >= 400:
        detail = _paddle_error_detail(response)
        logger.warning("Paddle API %s %s failed with %s: %s", method, path, response.status_code, detail)
        raise PaddleAPIError(detail or f"Paddle API request failed with status {response.status_code}")

    if not response.content:
        return {}
    payload = response.json()
    return payload.get("data", payload)


async def create_portal_session(
    settings: Settings,
    customer_id: str,
    subscription_ids: list[str],
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if subscription_ids:
        body["subscription_ids"] = subscription_ids
    return await paddle_api_request(settings, "POST", f"/customers/{customer_id}/portal-sessions", json_body=body)


async def update_subscription_plan(
    settings: Settings,
    subscription_id: str,
    price_id: str,
    *,
    quantity: int = 1,
    proration_billing_mode: str = "prorated_immediately",
) -> dict[str, Any]:
    return await paddle_api_request(
        settings,
        "PATCH",
        f"/subscriptions/{subscription_id}",
        json_body={
            "items": [{"price_id": price_id, "quantity": max(1, quantity)}],
            "proration_billing_mode": proration_billing_mode,
            "on_payment_failure": "prevent_change",
        },
    )


async def cancel_subscription(
    settings: Settings,
    subscription_id: str,
    *,
    effective_from: str = "next_billing_period",
) -> dict[str, Any]:
    return await paddle_api_request(
        settings,
        "POST",
        f"/subscriptions/{subscription_id}/cancel",
        json_body={"effective_from": effective_from},
    )


async def sync_customer_transactions(settings: Settings, db: Session, customer: PaddleCustomer) -> list[PaddleTransaction]:
    data = await paddle_api_request(
        settings,
        "GET",
        "/transactions",
        params={
            "customer_id": customer.customer_id,
            "per_page": 30,
            "order_by": "billed_at[DESC]",
        },
    )
    transactions = data if isinstance(data, list) else []
    synced = [upsert_transaction(db, item) for item in transactions]
    db.commit()
    return synced


def verify_paddle_signature(
    raw_body: bytes,
    signature_header: str,
    secret: str,
    *,
    tolerance_seconds: int = 300,
) -> None:
    if not secret:
        raise PaddleConfigurationError("PADDLE_WEBHOOK_SECRET is not configured")
    parsed = _parse_signature_header(signature_header)
    timestamp = parsed.get("ts", "")
    signatures = parsed.get("h1", [])
    if not timestamp or not signatures:
        raise ValueError("Missing Paddle signature timestamp or digest")
    try:
        signed_at = int(timestamp)
    except ValueError as exc:
        raise ValueError("Invalid Paddle signature timestamp") from exc
    if tolerance_seconds > 0 and abs(time.time() - signed_at) > tolerance_seconds:
        raise ValueError("Paddle webhook signature timestamp is outside the allowed tolerance")

    signed_payload = f"{timestamp}:{raw_body.decode('utf-8')}".encode("utf-8")
    expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, signature) for signature in signatures):
        raise ValueError("Invalid Paddle webhook signature")


def process_paddle_webhook(db: Session, payload: dict[str, Any], settings: Settings) -> dict[str, Any]:
    event_id = str(payload.get("event_id") or payload.get("id") or "")
    event_type = str(payload.get("event_type") or "")
    if not event_id or not event_type:
        raise ValueError("Paddle webhook payload is missing event_id or event_type")

    existing = db.get(PaddleWebhookEvent, event_id)
    if existing and existing.processed_at:
        return {"status": "duplicate", "event_id": event_id, "event_type": event_type}

    event = existing or PaddleWebhookEvent(
        id=event_id,
        event_type=event_type,
        occurred_at=_parse_datetime(payload.get("occurred_at")),
        raw=payload,
    )
    db.add(event)
    db.flush()

    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    if event_type.startswith("customer."):
        upsert_customer(db, data)
    elif event_type.startswith("subscription."):
        upsert_subscription(db, data, settings)
    elif event_type.startswith("transaction."):
        upsert_transaction(db, data)
    else:
        logger.info("Paddle webhook %s received with no local sync action", event_type)

    event.processed_at = utc_now()
    db.add(event)
    db.commit()
    return {"status": "processed", "event_id": event_id, "event_type": event_type}


def billing_overview(db: Session, user: User, settings: Settings) -> BillingOverview:
    customer = get_customer_for_user(db, user.id)
    subscription = get_primary_subscription_for_user(db, user.id)
    return BillingOverview(
        environment="sandbox" if settings.paddle_is_sandbox else "production",
        customer=_customer_read(customer) if customer else None,
        subscription=_subscription_read(subscription) if subscription else None,
        plans=billing_plans(settings),
    )


def subscription_access_plan(subscription: PaddleSubscription) -> str:
    return subscription.plan_key if subscription_access_active(subscription) else "none"


def subscription_access_until(subscription: PaddleSubscription) -> datetime | None:
    return subscription.current_period_ends_at or subscription.next_billed_at


def subscription_access_active(subscription: PaddleSubscription) -> bool:
    status = (subscription.status or "").lower()
    if status in {"active", "trialing", "past_due"}:
        return True
    if status == "canceled" and _future_datetime(subscription.current_period_ends_at):
        return True
    return False


def billing_history(db: Session, user: User) -> list[PaddleTransactionRead]:
    transactions = db.scalars(
        select(PaddleTransaction)
        .where(PaddleTransaction.user_id == user.id)
        .order_by(desc(PaddleTransaction.billed_at), desc(PaddleTransaction.created_at))
        .limit(30)
    ).all()
    return [_transaction_read(transaction) for transaction in transactions]


def get_customer_for_user(db: Session, user_id: str) -> PaddleCustomer | None:
    return db.scalar(select(PaddleCustomer).where(PaddleCustomer.user_id == user_id).limit(1))


def get_primary_subscription_for_user(db: Session, user_id: str) -> PaddleSubscription | None:
    subscriptions = db.scalars(
        select(PaddleSubscription)
        .where(PaddleSubscription.user_id == user_id)
        .order_by(desc(PaddleSubscription.created_at))
    ).all()
    preferred = {"active", "trialing", "past_due", "paused"}
    return (
        next((item for item in subscriptions if (item.status or "").lower() in preferred), None)
        or next((item for item in subscriptions if subscription_access_active(item)), None)
        or (subscriptions[0] if subscriptions else None)
    )


def get_owned_subscription(db: Session, user_id: str, subscription_id: str) -> PaddleSubscription | None:
    return db.scalar(
        select(PaddleSubscription)
        .where(PaddleSubscription.user_id == user_id, PaddleSubscription.subscription_id == subscription_id)
        .limit(1)
    )


def upsert_customer(db: Session, data: dict[str, Any]) -> PaddleCustomer:
    customer_id = str(data.get("id") or data.get("customer_id") or "")
    if not customer_id:
        raise ValueError("Paddle customer payload is missing id")
    email = normalize_email(str(data.get("email") or ""))
    user = _find_user(db, _custom_data_user_id(data), email)

    customer = db.scalar(select(PaddleCustomer).where(PaddleCustomer.customer_id == customer_id).limit(1))
    if not customer and user:
        customer = db.scalar(select(PaddleCustomer).where(PaddleCustomer.user_id == user.id).limit(1))
    if not customer:
        customer = PaddleCustomer(customer_id=customer_id)

    customer.customer_id = customer_id
    customer.email = email
    customer.name = str(data.get("name") or "")
    customer.status = str(data.get("status") or "")
    customer.raw = data
    if user:
        customer.user_id = user.id

    db.add(customer)
    db.flush()
    return customer


def upsert_subscription(db: Session, data: dict[str, Any], settings: Settings) -> PaddleSubscription:
    subscription_id = str(data.get("id") or data.get("subscription_id") or "")
    if not subscription_id:
        raise ValueError("Paddle subscription payload is missing id")
    customer_id = str(data.get("customer_id") or "")
    customer = db.scalar(select(PaddleCustomer).where(PaddleCustomer.customer_id == customer_id).limit(1)) if customer_id else None
    user = _find_user(db, _custom_data_user_id(data), "")
    if not user and customer and customer.user_id:
        user = db.get(User, customer.user_id)
    if customer_id and not customer:
        customer = PaddleCustomer(customer_id=customer_id)
        customer.email = normalize_email(user.email) if user else ""
        if user:
            customer.user_id = user.id
        db.add(customer)
        db.flush()

    subscription = db.scalar(
        select(PaddleSubscription).where(PaddleSubscription.subscription_id == subscription_id).limit(1)
    )
    if not subscription:
        subscription = PaddleSubscription(subscription_id=subscription_id)

    price_id, product_id, quantity = _subscription_price_details(data)
    plan = find_plan_by_price_id(settings, price_id)
    billing_cycle = data.get("billing_cycle") if isinstance(data.get("billing_cycle"), dict) else {}
    current_period = (
        data.get("current_billing_period") if isinstance(data.get("current_billing_period"), dict) else {}
    )
    scheduled_change = data.get("scheduled_change") if isinstance(data.get("scheduled_change"), dict) else {}

    subscription.customer_id = customer_id
    subscription.status = str(data.get("status") or "")
    subscription.plan_key = plan.key if plan else ""
    subscription.price_id = price_id
    subscription.product_id = product_id
    subscription.quantity = quantity
    subscription.currency_code = str(data.get("currency_code") or "")
    subscription.billing_interval = str(billing_cycle.get("interval") or "")
    subscription.billing_frequency = int(billing_cycle.get("frequency") or 1)
    subscription.started_at = _parse_datetime(data.get("started_at"))
    subscription.first_billed_at = _parse_datetime(data.get("first_billed_at"))
    subscription.next_billed_at = _parse_datetime(data.get("next_billed_at"))
    subscription.current_period_starts_at = _parse_datetime(current_period.get("starts_at"))
    subscription.current_period_ends_at = _parse_datetime(current_period.get("ends_at"))
    subscription.paused_at = _parse_datetime(data.get("paused_at"))
    subscription.canceled_at = _parse_datetime(data.get("canceled_at"))
    subscription.scheduled_change_action = str(scheduled_change.get("action") or "")
    subscription.scheduled_change_effective_at = _parse_datetime(scheduled_change.get("effective_at"))
    subscription.management_urls = data.get("management_urls") if isinstance(data.get("management_urls"), dict) else {}
    subscription.items = data.get("items") if isinstance(data.get("items"), list) else []
    subscription.custom_data = data.get("custom_data") if isinstance(data.get("custom_data"), dict) else {}
    subscription.raw = data
    if user:
        subscription.user_id = user.id
        if customer:
            customer.user_id = user.id
            db.add(customer)

    db.add(subscription)
    db.flush()
    return subscription


def upsert_transaction(db: Session, data: dict[str, Any]) -> PaddleTransaction:
    transaction_id = str(data.get("id") or data.get("transaction_id") or "")
    if not transaction_id:
        raise ValueError("Paddle transaction payload is missing id")
    customer_id = str(data.get("customer_id") or "")
    subscription_id = str(data.get("subscription_id") or "")
    customer = db.scalar(select(PaddleCustomer).where(PaddleCustomer.customer_id == customer_id).limit(1)) if customer_id else None
    subscription = (
        db.scalar(select(PaddleSubscription).where(PaddleSubscription.subscription_id == subscription_id).limit(1))
        if subscription_id
        else None
    )
    user = _find_user(db, _custom_data_user_id(data), "")
    if not user and subscription and subscription.user_id:
        user = db.get(User, subscription.user_id)
    if not user and customer and customer.user_id:
        user = db.get(User, customer.user_id)
    if customer_id and not customer:
        customer = PaddleCustomer(customer_id=customer_id)
        customer.email = normalize_email(user.email) if user else ""
        if user:
            customer.user_id = user.id
        db.add(customer)
        db.flush()
    elif customer and user and not customer.user_id:
        customer.user_id = user.id
        db.add(customer)

    transaction = db.scalar(select(PaddleTransaction).where(PaddleTransaction.transaction_id == transaction_id).limit(1))
    if not transaction:
        transaction = PaddleTransaction(transaction_id=transaction_id)

    details = data.get("details") if isinstance(data.get("details"), dict) else {}
    totals = details.get("totals") if isinstance(details.get("totals"), dict) else {}
    checkout = data.get("checkout") if isinstance(data.get("checkout"), dict) else {}

    transaction.customer_id = customer_id
    transaction.subscription_id = subscription_id
    transaction.status = str(data.get("status") or "")
    transaction.invoice_number = str(data.get("invoice_number") or "")
    transaction.currency_code = str(data.get("currency_code") or totals.get("currency_code") or "")
    transaction.subtotal = str(totals.get("subtotal") or "")
    transaction.tax = str(totals.get("tax") or "")
    transaction.total = str(totals.get("total") or totals.get("grand_total") or "")
    transaction.billed_at = _parse_datetime(data.get("billed_at"))
    transaction.invoice_url = str(checkout.get("url") or "")
    transaction.raw = data
    if user:
        transaction.user_id = user.id

    db.add(transaction)
    db.flush()
    return transaction


def subscription_read(subscription: PaddleSubscription) -> PaddleSubscriptionRead:
    return _subscription_read(subscription)


def _customer_read(customer: PaddleCustomer) -> PaddleCustomerRead:
    return PaddleCustomerRead(
        customer_id=customer.customer_id,
        email=customer.email,
        name=customer.name,
        status=customer.status,
    )


def _subscription_read(subscription: PaddleSubscription) -> PaddleSubscriptionRead:
    access_until = subscription_access_until(subscription)
    return PaddleSubscriptionRead(
        subscription_id=subscription.subscription_id,
        customer_id=subscription.customer_id,
        status=subscription.status,
        plan_key=subscription.plan_key,
        price_id=subscription.price_id,
        product_id=subscription.product_id,
        quantity=subscription.quantity,
        currency_code=subscription.currency_code,
        billing_interval=subscription.billing_interval,
        billing_frequency=subscription.billing_frequency,
        started_at=subscription.started_at,
        first_billed_at=subscription.first_billed_at,
        next_billed_at=subscription.next_billed_at,
        current_period_starts_at=subscription.current_period_starts_at,
        current_period_ends_at=subscription.current_period_ends_at,
        paused_at=subscription.paused_at,
        canceled_at=subscription.canceled_at,
        scheduled_change_action=subscription.scheduled_change_action,
        scheduled_change_effective_at=subscription.scheduled_change_effective_at,
        management_urls=subscription.management_urls or {},
        access_plan=subscription_access_plan(subscription),
        access_until=access_until,
        access_active=subscription_access_active(subscription),
        cancel_at_period_end=subscription.scheduled_change_action == "cancel",
    )


def _transaction_read(transaction: PaddleTransaction) -> PaddleTransactionRead:
    return PaddleTransactionRead(
        transaction_id=transaction.transaction_id,
        customer_id=transaction.customer_id,
        subscription_id=transaction.subscription_id,
        status=transaction.status,
        invoice_number=transaction.invoice_number,
        currency_code=transaction.currency_code,
        subtotal=transaction.subtotal,
        tax=transaction.tax,
        total=transaction.total,
        billed_at=transaction.billed_at,
        invoice_url=transaction.invoice_url,
    )


def _find_user(db: Session, user_id: str, email: str) -> User | None:
    if user_id:
        user = db.get(User, user_id)
        if user:
            return user
    if email:
        return db.scalar(select(User).where(User.email == normalize_email(email)).limit(1))
    return None


def _custom_data_user_id(data: dict[str, Any]) -> str:
    custom_data = data.get("custom_data") if isinstance(data.get("custom_data"), dict) else {}
    for key in ("leadforge_user_id", "user_id", "userId"):
        value = custom_data.get(key)
        if value:
            return str(value)
    return ""


def _subscription_price_details(data: dict[str, Any]) -> tuple[str, str, int]:
    items = data.get("items") if isinstance(data.get("items"), list) else []
    if not items:
        return "", "", 1
    item = items[0] if isinstance(items[0], dict) else {}
    price = item.get("price") if isinstance(item.get("price"), dict) else {}
    price_id = str(price.get("id") or item.get("price_id") or "")
    product_id = str(price.get("product_id") or item.get("product_id") or "")
    try:
        quantity = int(item.get("quantity") or 1)
    except (TypeError, ValueError):
        quantity = 1
    return price_id, product_id, max(1, quantity)


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _future_datetime(value: datetime | None) -> bool:
    if not value:
        return False
    return as_utc(value) > utc_now()


def _absolute_frontend_url(settings: Settings, value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith(("http://", "https://")):
        return cleaned
    path = cleaned if cleaned.startswith("/") else f"/{cleaned}"
    base = settings.frontend_origin or settings.public_backend_url or "http://localhost:3000"
    return f"{base.rstrip('/')}{path}"


def _parse_signature_header(header: str) -> dict[str, list[str] | str]:
    parsed: dict[str, list[str] | str] = {}
    for part in header.replace(",", ";").split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key == "h1":
            current = parsed.setdefault("h1", [])
            if isinstance(current, list):
                current.append(value)
        elif key:
            parsed[key] = value
    return parsed


def _paddle_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return response.text[:300]
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        detail = error.get("detail") or error.get("message") or error.get("type")
        if detail:
            return str(detail)
    if isinstance(payload, dict) and payload.get("message"):
        return str(payload["message"])
    return response.text[:300]
