"""Threshold configuration.

The brief's point is that the investor decides what 'unusual' means, so this
is a first-class screen, not a settings afterthought. Changing a threshold
re-evaluates immediately rather than waiting for the next nightly run.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Announcement, Company, PriceBar
from app.db.session import get_session
from app.schemas.digest import AlertRuleIn, AlertRuleOut
from app.services.classification.taxonomy import CATEGORY_WEIGHT, label_for
from app.services.ingest.runner import fire_alerts, get_rule
from app.utils.dates import utcnow

router = APIRouter(prefix="/alert-rules", tags=["push"])


@router.get("", response_model=AlertRuleOut)
def read_rule(session: Session = Depends(get_session)) -> AlertRuleOut:
    rule = get_rule(session)
    session.commit()
    return AlertRuleOut(
        profile=rule.profile,
        volume_multiple=rule.volume_multiple,
        price_move_pct=rule.price_move_pct,
        watched_categories=rule.category_list,
        min_score=rule.min_score,
        enabled=rule.enabled,
    )


@router.put("", response_model=AlertRuleOut)
def update_rule(
    payload: AlertRuleIn, session: Session = Depends(get_session)
) -> AlertRuleOut:
    rule = get_rule(session)
    rule.volume_multiple = payload.volume_multiple
    rule.price_move_pct = payload.price_move_pct
    rule.min_score = payload.min_score
    rule.enabled = payload.enabled

    # Silently drop categories that are not in the taxonomy rather than
    # rejecting the whole update: a stale client should still be able to
    # change its thresholds.
    valid = [c for c in payload.watched_categories if c in CATEGORY_WEIGHT]
    rule.watched_categories = ",".join(valid)
    session.flush()

    # Re-evaluate now so the user sees the effect of their change at once.
    recent = list(
        session.scalars(
            select(Announcement)
            .where(Announcement.filed_at >= utcnow().replace(hour=0, minute=0))
            .limit(200)
        )
    )
    fire_alerts(session, recent)
    session.commit()

    return AlertRuleOut(
        profile=rule.profile,
        volume_multiple=rule.volume_multiple,
        price_move_pct=rule.price_move_pct,
        watched_categories=rule.category_list,
        min_score=rule.min_score,
        enabled=rule.enabled,
    )


@router.get("/categories", response_model=list[dict])
def list_categories() -> list[dict]:
    """Subscribable categories, ordered by how much they usually matter."""
    return [
        {"value": key, "label": label_for(key), "default_weight": weight}
        for key, weight in sorted(
            CATEGORY_WEIGHT.items(), key=lambda kv: kv[1], reverse=True
        )
    ]


@router.get("/preview", response_model=dict)
def preview(
    volume_multiple: float = 2.0,
    price_move_pct: float = 4.0,
    session: Session = Depends(get_session),
) -> dict:
    """How many alerts these thresholds would have fired recently.

    Tuning a threshold blind is guesswork; this turns the settings screen
    into something the investor can calibrate against their own portfolio.
    """
    bars = list(
        session.execute(
            select(PriceBar, Company)
            .join(Company, Company.id == PriceBar.company_id)
            .where(Company.in_portfolio.is_(True))
        ).all()
    )
    price_hits = sum(
        1
        for bar, _ in bars
        if bar.pct_change is not None and abs(bar.pct_change) >= price_move_pct
    )
    volume_hits = sum(
        1
        for bar, _ in bars
        if bar.volume_ratio is not None and bar.volume_ratio >= volume_multiple
    )
    days = len({bar.trade_date for bar, _ in bars}) or 1
    return {
        "days_observed": days,
        "price_alerts": price_hits,
        "volume_alerts": volume_hits,
        "per_day": round((price_hits + volume_hits) / days, 1),
    }
