"""Push endpoints: the windowed digest and the alert feed."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AlertEvent, Announcement, Company, PriceBar
from app.db.session import get_session
from app.schemas.digest import AlertOut, AnnouncementOut, DigestOut
from app.services.classification.taxonomy import label_for
from app.services.ranking.scorer import headline_count
from app.utils.dates import utcnow, window_start

router = APIRouter(prefix="/digest", tags=["push"])

# Above this, the first screen stops being a triage surface and becomes a
# second inbox. Overflow is still reachable under the routine fold.
_MATERIAL_CAP = 10


def _same_day_market(session: Session, company_id: int, when: datetime) -> PriceBar | None:
    """The bar for the filing's own trading day, for context on the card."""
    return session.scalars(
        select(PriceBar)
        .where(PriceBar.company_id == company_id, PriceBar.trade_date <= when.date())
        .order_by(PriceBar.trade_date.desc())
        .limit(1)
    ).first()


def _serialise(
    session: Session, announcement: Announcement, company: Company
) -> AnnouncementOut:
    bar = _same_day_market(session, company.id, announcement.filed_at)
    return AnnouncementOut(
        id=announcement.id,
        symbol=company.symbol,
        company_name=company.name,
        filed_at=announcement.filed_at,
        subject=announcement.subject,
        summary=announcement.summary,
        category=announcement.category,
        category_label=label_for(announcement.category),
        score=announcement.score,
        is_routine=announcement.is_routine,
        attachment_url=announcement.attachment_url,
        source=announcement.source,
        pct_change=bar.pct_change if bar else None,
        volume_ratio=bar.volume_ratio if bar else None,
        enrichment=announcement.enrichment,
    )


def _headline(material_count: int, routine_count: int, window_hours: int) -> str:
    """The sentence at the top of the app.

    Written to be honest on a quiet day. Manufacturing urgency when nothing
    happened is exactly the behaviour the product exists to avoid.
    """
    period = "since yesterday" if window_hours <= 24 else f"in the last {window_hours // 24} days"
    if material_count == 0 and routine_count == 0:
        return f"Nothing filed across your portfolio {period}."
    if material_count == 0:
        return f"Nothing that matters {period} — {routine_count} routine filings."
    noun = "thing" if material_count == 1 else "things"
    return f"{material_count} {noun} matter {period}."


@router.get("", response_model=DigestOut)
def get_digest(
    hours: int = Query(default=24, ge=1, le=2160, description="Lookback window"),
    include_non_portfolio: bool = Query(default=False),
    session: Session = Depends(get_session),
) -> DigestOut:
    """Every filing in a window, prioritised, with routine items separated."""
    start = window_start(hours)
    now = utcnow()

    query = (
        select(Announcement, Company)
        .join(Company, Company.id == Announcement.company_id)
        .where(Announcement.filed_at >= start)
        .order_by(Announcement.score.desc(), Announcement.filed_at.desc())
    )
    if not include_non_portfolio:
        query = query.where(Company.in_portfolio.is_(True))

    rows = session.execute(query).all()
    material: list[AnnouncementOut] = []
    routine: list[AnnouncementOut] = []

    for announcement, company in rows:
        payload = _serialise(session, announcement, company)
        (routine if announcement.is_routine else material).append(payload)

    # Cap the material list so the first screen stays a triage surface, not a
    # second inbox. Everything below the cap is still reachable in routine.
    overflow = material[_MATERIAL_CAP:]
    material = material[:_MATERIAL_CAP]
    routine = overflow + routine

    # The headline counts only what genuinely clears the bar — not simply
    # everything on screen. Ten middling filings is not "ten things matter".
    truly_material = headline_count([m.score for m in material])

    return DigestOut(
        window_hours=hours,
        from_ts=start,
        to_ts=now,
        headline=_headline(truly_material, len(routine) + len(material) - truly_material, hours),
        material=material,
        routine=routine,
        routine_count=len(routine),
        companies_affected=len({m.symbol for m in material}),
    )


@router.get("/alerts", response_model=list[AlertOut])
def get_alerts(
    limit: int = Query(default=25, ge=1, le=100),
    unacknowledged_only: bool = Query(default=False),
    session: Session = Depends(get_session),
) -> list[AlertOut]:
    query = (
        select(AlertEvent, Company)
        .join(Company, Company.id == AlertEvent.company_id)
        .order_by(AlertEvent.triggered_at.desc(), AlertEvent.severity.desc())
        .limit(limit)
    )
    if unacknowledged_only:
        query = query.where(AlertEvent.acknowledged.is_(False))

    return [
        AlertOut(
            id=event.id,
            symbol=company.symbol,
            company_name=company.name,
            kind=event.kind,
            headline=event.headline,
            detail=event.detail,
            severity=event.severity,
            triggered_at=event.triggered_at,
            acknowledged=event.acknowledged,
            announcement_id=event.announcement_id,
        )
        for event, company in session.execute(query).all()
    ]


@router.post("/alerts/{alert_id}/ack", response_model=dict)
def acknowledge(alert_id: int, session: Session = Depends(get_session)) -> dict:
    event = session.get(AlertEvent, alert_id)
    if event is None:
        return {"ok": False, "detail": "No such alert."}
    event.acknowledged = True
    session.commit()
    return {"ok": True}


@router.get("/stats", response_model=dict)
def digest_stats(session: Session = Depends(get_session)) -> dict:
    """Counts used by the empty states, so the UI can say something useful
    instead of showing a blank screen."""
    total = session.scalar(select(func.count(Announcement.id))) or 0
    companies = session.scalar(select(func.count(Company.id))) or 0
    newest = session.scalar(select(func.max(Announcement.filed_at)))
    return {
        "announcements": total,
        "companies": companies,
        "latest_filing": newest.isoformat() if newest else None,
    }
