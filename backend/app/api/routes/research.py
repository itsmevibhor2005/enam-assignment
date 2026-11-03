"""Pull endpoints: on-demand analysis of any NSE ticker."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import InsufficientData
from app.core.logging import get_logger
from app.db.models import Company
from app.db.session import get_session
from app.schemas.research import (
    GuidanceItem,
    GuidanceScorecard,
    ResearchOut,
    SnapshotOut,
    SourceRef,
)
from app.services.analysis import guidance as guidance_service
from app.services.analysis import research as research_service

log = get_logger(__name__)
router = APIRouter(prefix="/research", tags=["pull"])


def _format_promise(claim) -> str:
    """Render a stored claim back into readable English."""
    unit = {"pct": "%", "crore": " cr", "x": "x"}.get(claim.unit or "", "")
    if claim.target_low is not None and claim.target_high is not None:
        if claim.target_low == claim.target_high:
            target = f"{claim.target_low:g}{unit}"
        else:
            target = f"{claim.target_low:g}-{claim.target_high:g}{unit}"
    elif claim.target_low is not None:
        target = f"at least {claim.target_low:g}{unit}"
    elif claim.target_high is not None:
        target = f"up to {claim.target_high:g}{unit}"
    else:
        target = {"grow": "to grow", "expand": "to expand",
                  "contract": "to contract", "flat": "to stay flat"}.get(
            claim.direction or "", "directional"
        )
    return f"{claim.metric} {target}".strip()


@router.get("/{symbol}", response_model=ResearchOut)
async def research(
    symbol: str,
    quarters: int = Query(default=4, ge=1, le=8),
    session: Session = Depends(get_session),
) -> ResearchOut:
    """Full research view, grounded only in annual reports and transcripts.

    Works for any NSE symbol; an unknown ticker is resolved and ingested on
    demand rather than rejected.
    """
    company = await research_service.resolve_company(session, symbol)
    session.commit()

    bundle = await research_service.build_bundle(session, company)
    session.commit()

    report = await guidance_service.build_report(session, company, quarters=quarters)
    session.commit()

    items: list[GuidanceItem] = []
    for record in report.records:
        claim = record.claim
        outcome = record.outcome
        horizon = (
            f"Q{claim.horizon_q or 4} FY{str(claim.horizon_fy)[-2:]}"
            if claim.horizon_fy
            else None
        )
        items.append(
            GuidanceItem(
                claim_id=claim.id,
                said_in=f"Q{claim.said_q} FY{str(claim.said_fy)[-2:]}",
                metric=claim.metric,
                promise=_format_promise(claim),
                horizon=horizon,
                speaker=claim.speaker,
                quote=claim.quote,
                status=outcome.status if outcome else "too_early",
                actual_value=outcome.actual_value if outcome else None,
                reasoning=outcome.reasoning if outcome else None,
                confidence=outcome.confidence if outcome else 0.5,
            )
        )

    # Newest promises first, but unresolved ones sink: the investor cares
    # most about what has already been settled.
    order = {"missed": 0, "partial": 1, "met": 2, "unverifiable": 3, "too_early": 4}
    items.sort(key=lambda i: (order.get(i.status, 5), i.said_in), reverse=False)

    return ResearchOut(
        symbol=company.symbol,
        name=company.name,
        in_portfolio=company.in_portfolio,
        snapshot=SnapshotOut(**bundle.snapshot) if bundle.snapshot else None,
        bull=(bundle.bull_bear or {}).get("bull", []),
        bear=(bundle.bull_bear or {}).get("bear", []),
        guidance=items,
        scorecard=GuidanceScorecard(**report.scorecard) if report.scorecard else GuidanceScorecard(),
        quarters_covered=report.quarters_covered,
        sources=[SourceRef(**s) for s in bundle.sources],
        warnings=bundle.warnings,
        guidance_note=report.note,
    )


@router.get("", response_model=list[dict])
def list_companies(session: Session = Depends(get_session)) -> list[dict]:
    """Tickers available for one-tap research, portfolio first."""
    companies = session.scalars(
        select(Company).order_by(Company.in_portfolio.desc(), Company.symbol)
    )
    return [
        {
            "symbol": c.symbol,
            "name": c.name,
            "sector": c.sector,
            "in_portfolio": c.in_portfolio,
        }
        for c in companies
    ]
