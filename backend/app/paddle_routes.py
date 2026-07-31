"""FastAPI routes for LeadForge Paddle Billing."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .auth import get_current_user
from .config import Settings, get_settings
from .database import get_db
from .models import User
from .paddle_billing import (
    PaddleAPIError,
    PaddleConfigurationError,
    billing_history,
    billing_overview,
    billing_plans_response,
    cancel_subscription,
    create_portal_session,
    find_plan_by_price_id,
    get_customer_for_user,
    get_owned_subscription,
    process_paddle_webhook,
    subscription_read,
    sync_customer_transactions,
    update_subscription_plan,
    upsert_subscription,
    verify_paddle_signature,
)
from .schemas import (
    BillingHistoryResponse,
    BillingOverview,
    BillingPlansResponse,
    PaddleCancelSubscriptionRequest,
    PaddleChangePlanRequest,
    PaddlePortalSessionResponse,
    PaddleSubscriptionRead,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans", response_model=BillingPlansResponse)
def get_billing_plans(settings: Settings = Depends(get_settings)) -> BillingPlansResponse:
    return billing_plans_response(settings)


@router.get("/me", response_model=BillingOverview)
def get_my_billing(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> BillingOverview:
    return billing_overview(db, current_user, settings)


@router.get("/history", response_model=BillingHistoryResponse)
async def get_my_billing_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> BillingHistoryResponse:
    customer = get_customer_for_user(db, current_user.id)
    if customer and settings.paddle_api_key:
        try:
            await sync_customer_transactions(settings, db, customer)
        except (PaddleAPIError, PaddleConfigurationError):
            logger.exception("Unable to refresh Paddle transaction history for user %s", current_user.id)
    return BillingHistoryResponse(transactions=billing_history(db, current_user))


@router.post("/portal-session", response_model=PaddlePortalSessionResponse)
async def create_my_portal_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> PaddlePortalSessionResponse:
    customer = get_customer_for_user(db, current_user.id)
    if not customer:
        raise HTTPException(status_code=404, detail="No Paddle customer is connected to this account yet")
    overview = billing_overview(db, current_user, settings)
    subscription_ids = [overview.subscription.subscription_id] if overview.subscription else []
    try:
        session = await create_portal_session(settings, customer.customer_id, subscription_ids)
    except PaddleConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PaddleAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    urls = session.get("urls") if isinstance(session.get("urls"), dict) else {}
    general = urls.get("general") if isinstance(urls.get("general"), dict) else {}
    url = str(general.get("overview") or urls.get("overview") or "")
    if not url:
        raise HTTPException(status_code=502, detail="Paddle did not return a customer portal URL")
    return PaddlePortalSessionResponse(url=url, urls=urls)


@router.post("/subscriptions/{subscription_id}/change-plan", response_model=PaddleSubscriptionRead)
async def change_subscription_plan(
    subscription_id: str,
    payload: PaddleChangePlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> PaddleSubscriptionRead:
    subscription = get_owned_subscription(db, current_user.id, subscription_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if not find_plan_by_price_id(settings, payload.price_id):
        raise HTTPException(status_code=400, detail="Unknown Paddle price ID for this LeadForge billing catalog")
    try:
        updated = await update_subscription_plan(
            settings,
            subscription.subscription_id,
            payload.price_id,
            quantity=subscription.quantity,
            proration_billing_mode=payload.proration_billing_mode,
        )
    except PaddleConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PaddleAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    synced = upsert_subscription(db, updated, settings)
    db.commit()
    db.refresh(synced)
    return subscription_read(synced)


@router.post("/subscriptions/{subscription_id}/cancel", response_model=PaddleSubscriptionRead)
async def cancel_my_subscription(
    subscription_id: str,
    payload: PaddleCancelSubscriptionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> PaddleSubscriptionRead:
    subscription = get_owned_subscription(db, current_user.id, subscription_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    try:
        updated = await cancel_subscription(
            settings,
            subscription.subscription_id,
            effective_from=payload.effective_from,
        )
    except PaddleConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PaddleAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    synced = upsert_subscription(db, updated, settings)
    db.commit()
    db.refresh(synced)
    return subscription_read(synced)


@router.post("/webhook")
async def paddle_webhook(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    raw_body = await request.body()
    signature = request.headers.get("Paddle-Signature", "")
    try:
        verify_paddle_signature(
            raw_body,
            signature,
            settings.paddle_webhook_secret,
            tolerance_seconds=settings.paddle_webhook_tolerance_seconds,
        )
        payload = json.loads(raw_body.decode("utf-8"))
        result = process_paddle_webhook(db, payload, settings)
    except PaddleConfigurationError as exc:
        logger.exception("Paddle webhook rejected because verification is not configured")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Invalid Paddle webhook payload: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid Paddle webhook") from exc
    except Exception as exc:
        logger.exception("Paddle webhook processing failed")
        raise HTTPException(status_code=500, detail="Paddle webhook processing failed") from exc
    return result
