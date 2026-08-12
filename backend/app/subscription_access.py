"""Subscription entitlements and usage enforcement for LeadForge.

This module keeps plan rules in one place and derives access from the existing
Paddle subscription records. It does not own billing state; Paddle remains the
source for subscription status, while this layer answers "can this user do X?"
for API routes and frontend gating.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import get_current_user, utc_now
from .database import get_db
from .models import Lead, Outreach, User
from .paddle_billing import (
    get_primary_subscription_for_user,
    subscription_access_active,
    subscription_access_plan,
    subscription_access_until,
)

PlanKey = Literal["none", "basic", "agent", "agency"]
FeatureKey = Literal[
    "lead_generation",
    "standard_filters",
    "advanced_filters",
    "crm",
    "analytics",
    "csv_export",
    "outreach",
    "campaigns",
    "campaign_automation",
    "ai_sdr",
    "twilio",
    "reply_sync",
    "premium_enrichment",
    "unlimited_outreach",
]

PLAN_ORDER: dict[str, int] = {
    "none": 0,
    "basic": 1,
    "agent": 2,
    "agency": 3,
}

PLAN_NAMES: dict[str, str] = {
    "none": "No active plan",
    "basic": "Basic",
    "agent": "Agent",
    "agency": "Agency",
}

PLAN_LEAD_LIMITS: dict[str, int] = {
    "none": 0,
    "basic": 400,
    "agent": 800,
    "agency": 1500,
}

PLAN_OUTREACH_DAILY_LIMITS: dict[str, int | None] = {
    "none": 0,
    "basic": 7,
    "agent": 20,
    "agency": None,
}

ADMIN_LEAD_LIMIT = 1_000_000

FEATURE_REQUIREMENTS: dict[FeatureKey, PlanKey] = {
    "lead_generation": "basic",
    "standard_filters": "basic",
    "advanced_filters": "agent",
    "crm": "basic",
    "analytics": "basic",
    "csv_export": "basic",
    "outreach": "basic",
    "campaigns": "agent",
    "campaign_automation": "agency",
    "ai_sdr": "agency",
    "twilio": "agency",
    "reply_sync": "agency",
    "premium_enrichment": "agency",
    "unlimited_outreach": "agency",
}

FEATURE_LABELS: dict[str, str] = {
    "lead_generation": "Lead Generation",
    "standard_filters": "Standard Filters",
    "advanced_filters": "Advanced Filters",
    "crm": "CRM",
    "analytics": "Analytics",
    "csv_export": "CSV Export",
    "outreach": "Outreach",
    "campaigns": "Campaigns",
    "campaign_automation": "Campaign Automation",
    "ai_sdr": "AI SDR",
    "twilio": "Automated Calling",
    "reply_sync": "Reply Sync",
    "premium_enrichment": "Premium Enrichment",
    "unlimited_outreach": "Unlimited Outreach",
}

UPGRADE_BENEFITS: dict[str, list[str]] = {
    "crm": ["CRM pipeline", "Lead notes and stages", "Follow-up tracking"],
    "analytics": ["Analytics dashboard", "Performance charts", "Conversion reporting"],
    "csv_export": ["CSV export", "Campaign exports", "Lead data download"],
    "outreach": ["Gmail outreach", "AI email drafts", "Daily sending quota"],
    "campaigns": ["Campaign management", "Campaign exports", "Performance history"],
    "ai_sdr": ["AI SDR", "Automated calling", "Conversation workspace"],
    "twilio": ["Twilio calling connection", "Voice settings", "AI SDR calls"],
    "reply_sync": ["Reply sync", "Inbox tracking", "CRM reply updates"],
    "advanced_filters": ["Advanced filters", "Social/contact filters", "Campaign targeting"],
    "campaign_automation": ["Campaign automation", "Automated workflows", "Agency operations"],
    "premium_enrichment": ["Premium enrichment", "Deeper lead context", "Advanced scoring"],
    "unlimited_outreach": ["Unlimited outreach", "Higher sending volume", "Agency campaigns"],
}


def normalize_plan_key(value: str | None) -> PlanKey:
    key = (value or "").strip().lower()
    return key if key in PLAN_ORDER else "none"  # type: ignore[return-value]


def plan_includes(current_plan: str, required_plan: str) -> bool:
    return PLAN_ORDER[normalize_plan_key(current_plan)] >= PLAN_ORDER[normalize_plan_key(required_plan)]


def current_plan_key(db: Session, user: User) -> PlanKey:
    if user.is_admin:
        return "agency"
    subscription = get_primary_subscription_for_user(db, user.id)
    if not subscription:
        return "none"
    return normalize_plan_key(subscription_access_plan(subscription))


def subscription_access_payload(db: Session, user: User) -> dict[str, Any]:
    if user.is_admin:
        leads_used = monthly_leads_used(db, user.id)
        outreach_sent_today = daily_outreach_sent(db, user.id)
        return {
            "plan_key": "agency",
            "plan_name": "Admin",
            "status": "admin",
            "access_active": True,
            "access_until": None,
            "lead_limit": ADMIN_LEAD_LIMIT,
            "leads_used": leads_used,
            "leads_remaining": max(ADMIN_LEAD_LIMIT - leads_used, 0),
            "outreach_daily_limit": None,
            "outreach_sent_today": outreach_sent_today,
            "outreach_remaining_today": None,
            "features": {feature: True for feature in FEATURE_REQUIREMENTS},
            "requirements": FEATURE_REQUIREMENTS,
            "feature_labels": FEATURE_LABELS,
        }
    subscription = get_primary_subscription_for_user(db, user.id)
    plan_key = normalize_plan_key(subscription_access_plan(subscription)) if subscription else "none"
    leads_used = monthly_leads_used(db, user.id)
    outreach_sent_today = daily_outreach_sent(db, user.id)
    lead_limit = PLAN_LEAD_LIMITS[plan_key]
    outreach_limit = PLAN_OUTREACH_DAILY_LIMITS[plan_key]
    features = {
        feature: plan_includes(plan_key, required_plan)
        for feature, required_plan in FEATURE_REQUIREMENTS.items()
    }
    return {
        "plan_key": plan_key,
        "plan_name": PLAN_NAMES[plan_key],
        "status": subscription.status if subscription else "no_subscription",
        "access_active": bool(subscription_access_active(subscription)) if subscription else False,
        "access_until": subscription_access_until(subscription) if subscription else None,
        "lead_limit": lead_limit,
        "leads_used": leads_used,
        "leads_remaining": max(lead_limit - leads_used, 0),
        "outreach_daily_limit": outreach_limit,
        "outreach_sent_today": outreach_sent_today,
        "outreach_remaining_today": None if outreach_limit is None else max(outreach_limit - outreach_sent_today, 0),
        "features": features,
        "requirements": FEATURE_REQUIREMENTS,
        "feature_labels": FEATURE_LABELS,
    }


def require_feature_dependency(feature: FeatureKey):
    def dependency(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> None:
        require_feature(db, current_user, feature)

    return dependency


def require_feature_user(feature: FeatureKey):
    def dependency(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> User:
        require_feature(db, current_user, feature)
        return current_user

    return dependency


def require_feature(db: Session, user: User, feature: FeatureKey) -> None:
    if user.is_admin:
        return
    plan_key = current_plan_key(db, user)
    required_plan = FEATURE_REQUIREMENTS[feature]
    if plan_includes(plan_key, required_plan):
        return
    raise_subscription_required(feature, required_plan, plan_key)


def require_platform_access(db: Session, user: User) -> None:
    if user.is_admin:
        return
    plan_key = current_plan_key(db, user)
    if plan_includes(plan_key, "basic"):
        return
    raise_subscription_required("lead_generation", "basic", plan_key)


def assert_generate_leads_allowed(db: Session, user: User, *, requested_count: int, website_mode: str, campaign_name: str | None) -> None:
    if user.is_admin:
        return
    require_feature(db, user, "lead_generation")
    plan_key = current_plan_key(db, user)

    if website_mode == "allPlaces" and not plan_includes(plan_key, "agent"):
        raise_subscription_required("advanced_filters", "agent", plan_key)
    if campaign_name and not plan_includes(plan_key, "agent"):
        raise_subscription_required("campaigns", "agent", plan_key)

    lead_limit = PLAN_LEAD_LIMITS[plan_key]
    used = monthly_leads_used(db, user.id)
    remaining = max(lead_limit - used, 0)
    if requested_count > remaining:
        raise_limit_reached(
            feature="lead_generation",
            required_plan=_next_plan(plan_key),
            current_plan=plan_key,
            message=(
                f"You've reached your monthly lead limit. "
                f"{used}/{lead_limit} leads are already used this month."
            ),
            usage={
                "limit": lead_limit,
                "used": used,
                "remaining": remaining,
                "requested": requested_count,
            },
        )


def assert_lead_filters_allowed(
    db: Session,
    user: User,
    *,
    campaign_id: str,
    outreach_status: str,
    contact: str,
) -> None:
    if user.is_admin:
        return
    require_feature(db, user, "lead_generation")
    plan_key = current_plan_key(db, user)
    if campaign_id and not plan_includes(plan_key, "agent"):
        raise_subscription_required("campaigns", "agent", plan_key)
    if outreach_status and not plan_includes(plan_key, "basic"):
        raise_subscription_required("standard_filters", "basic", plan_key)
    if contact in {"email", "phone"} and not plan_includes(plan_key, "basic"):
        raise_subscription_required("standard_filters", "basic", plan_key)
    if contact == "social" and not plan_includes(plan_key, "agent"):
        raise_subscription_required("advanced_filters", "agent", plan_key)


def assert_outreach_send_allowed(db: Session, user: User) -> None:
    if user.is_admin:
        return
    require_feature(db, user, "outreach")
    plan_key = current_plan_key(db, user)
    daily_limit = PLAN_OUTREACH_DAILY_LIMITS[plan_key]
    if daily_limit is None:
        return
    sent_today = daily_outreach_sent(db, user.id)
    if sent_today >= daily_limit:
        raise_limit_reached(
            feature="outreach",
            required_plan=_next_plan(plan_key),
            current_plan=plan_key,
            message=(
                f"You've reached your daily outreach limit. "
                f"{sent_today}/{daily_limit} emails are already sent today."
            ),
            usage={
                "limit": daily_limit,
                "used": sent_today,
                "remaining": 0,
            },
        )


def monthly_leads_used(db: Session, user_id: str) -> int:
    return int(
        db.scalar(
            select(func.count(Lead.id)).where(
                Lead.user_id == user_id,
                Lead.created_at >= _month_start(),
            )
        )
        or 0
    )


def daily_outreach_sent(db: Session, user_id: str) -> int:
    return int(
        db.scalar(
            select(func.count(Outreach.id)).where(
                Outreach.user_id == user_id,
                Outreach.sent_at >= _day_start(),
            )
        )
        or 0
    )


def raise_subscription_required(feature: FeatureKey, required_plan: PlanKey, current_plan: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=_detail(
            code="subscription_required",
            feature=feature,
            required_plan=required_plan,
            current_plan=current_plan,
            message=f"This feature requires the {PLAN_NAMES[required_plan]} plan.",
        ),
    )


def raise_limit_reached(
    *,
    feature: FeatureKey,
    required_plan: PlanKey,
    current_plan: str,
    message: str,
    usage: dict[str, int],
) -> None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            **_detail(
                code="limit_reached",
                feature=feature,
                required_plan=required_plan,
                current_plan=current_plan,
                message=message,
            ),
            "usage": usage,
        },
    )


def _detail(
    *,
    code: str,
    feature: FeatureKey,
    required_plan: PlanKey,
    current_plan: str,
    message: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "feature": feature,
        "feature_label": FEATURE_LABELS.get(feature, feature.replace("_", " ").title()),
        "required_plan": required_plan,
        "required_plan_name": PLAN_NAMES[required_plan],
        "current_plan": normalize_plan_key(current_plan),
        "current_plan_name": PLAN_NAMES[normalize_plan_key(current_plan)],
        "message": message,
        "upgrade_benefits": UPGRADE_BENEFITS.get(feature, [FEATURE_LABELS.get(feature, "Premium access")]),
    }


def _month_start() -> datetime:
    now = utc_now()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _day_start() -> datetime:
    now = utc_now()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _next_plan(plan_key: str) -> PlanKey:
    plan = normalize_plan_key(plan_key)
    if plan == "none":
        return "basic"
    if plan == "basic":
        return "agent"
    return "agency"
