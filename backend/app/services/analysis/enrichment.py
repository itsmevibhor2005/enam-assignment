"""Push-side rich rendering.

Only two categories earn a heavy treatment, because only two reliably carry
information the subject line cannot: results (the four numbers) and
management changes (who the person is). Everything else gets a one-line
summary at most. That restraint is the product decision.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import Announcement, Company, QuarterlyResult
from app.llm.client import get_llm
from app.llm.prompts import classify as classify_prompts
from app.llm.prompts import enrich as enrich_prompts
from app.services.classification.taxonomy import SUMMARY_WORTHY, Category
from app.utils.dates import FiscalQuarter
from app.utils.numbers import margin_pct, parse_amount, pct_change
from app.utils.text import truncate

log = get_logger(__name__)

_METRICS = ("revenue", "ebitda", "pbt", "pat")


async def summarise(announcement: Announcement) -> str | None:
    """One line, only where it adds something."""
    if announcement.category not in SUMMARY_WORTHY:
        return None
    payload = await get_llm().complete_json(
        stage="announcement_summary",
        system=classify_prompts.SUMMARY_SYSTEM,
        prompt=classify_prompts.build_summary_prompt(announcement.subject, announcement.body),
        tier="cheap",
        max_tokens=120,
    )
    if not isinstance(payload, dict):
        return None
    summary = (payload.get("summary") or "").strip()
    return truncate(summary, 160) or None


def _comparison_block(current: dict, prev: dict, year_ago: dict) -> list[dict[str, Any]]:
    """Build the four-metric table with QoQ and YoY.

    Percentages come from app.utils.numbers.pct_change, which refuses to
    compute across a sign flip — a swing from loss to profit renders as a
    marker, not a meaningless 'up 340%'.
    """
    rows: list[dict[str, Any]] = []
    for metric in _METRICS:
        now = parse_amount(current.get(metric))
        previous = parse_amount(prev.get(metric))
        ago = parse_amount(year_ago.get(metric))
        rows.append(
            {
                "metric": metric,
                "value": now,
                "qoq_pct": pct_change(now, previous),
                "yoy_pct": pct_change(now, ago),
                "prev_quarter": previous,
                "year_ago": ago,
                "sign_flip": _is_sign_flip(now, ago) or _is_sign_flip(now, previous),
            }
        )
    return rows


def _is_sign_flip(current: float | None, base: float | None) -> bool:
    if current is None or base is None:
        return False
    return (current < 0 < base) or (base < 0 < current)


async def extract_results(
    session: Session, company: Company, announcement: Announcement, text: str
) -> dict[str, Any] | None:
    """Pull the four headline numbers out of a results filing.

    Uses the strong tier: this is the one push-side step where a wrong number
    is worse than no number.
    """
    if not text.strip():
        return None

    payload = await get_llm().complete_json(
        stage="results_extraction",
        system=enrich_prompts.RESULTS_SYSTEM,
        prompt=enrich_prompts.build_results_prompt(company.name, text),
        tier="strong",
        max_tokens=1600,
    )
    if not isinstance(payload, dict):
        return None

    period = payload.get("period") or {}
    try:
        quarter = FiscalQuarter(int(period["fy"]), int(period["q"]))
    except (KeyError, TypeError, ValueError):
        log.info("results extraction returned no usable period for %s", company.symbol)
        return None

    unit = payload.get("unit") or "crore"
    current = _scale(payload.get("current") or {}, unit)
    prev = _scale(payload.get("prev_quarter") or {}, unit)
    year_ago = _scale(payload.get("year_ago") or {}, unit)

    if all(current.get(m) is None for m in _METRICS):
        return None  # nothing extracted; better to show the raw filing

    _persist_result(session, company, quarter, current, payload, announcement)

    return {
        "type": "results",
        "period": quarter.label,
        "basis": payload.get("basis") or "consolidated",
        "unit": "Rs crore",
        "ebitda_derived": bool(payload.get("ebitda_derived")),
        "confidence": float(payload.get("confidence") or 0.5),
        "rows": _comparison_block(current, prev, year_ago),
        "ebitda_margin_pct": margin_pct(current.get("ebitda"), current.get("revenue")),
        "pat_margin_pct": margin_pct(current.get("pat"), current.get("revenue")),
    }


def _scale(block: dict, unit: str) -> dict[str, float | None]:
    return {metric: parse_amount(block.get(metric), unit) for metric in _METRICS}


def _persist_result(
    session: Session,
    company: Company,
    quarter: FiscalQuarter,
    current: dict,
    payload: dict,
    announcement: Announcement,
) -> None:
    """Store the quarter so the pull side can adjudicate guidance against it.

    The push and pull sides share one source of truth; extracting the same
    numbers twice would be both wasteful and a chance to disagree with
    ourselves.
    """
    from sqlalchemy import select

    existing = session.scalars(
        select(QuarterlyResult).where(
            QuarterlyResult.company_id == company.id,
            QuarterlyResult.fiscal_year == quarter.fy,
            QuarterlyResult.quarter == quarter.q,
        )
    ).first()
    confidence = float(payload.get("confidence") or 0.5)

    if existing is None:
        session.add(
            QuarterlyResult(
                company_id=company.id,
                fiscal_year=quarter.fy,
                quarter=quarter.q,
                revenue=current.get("revenue"),
                ebitda=current.get("ebitda"),
                pbt=current.get("pbt"),
                pat=current.get("pat"),
                ebitda_derived=bool(payload.get("ebitda_derived")),
                source_url=announcement.attachment_url,
                confidence=confidence,
            )
        )
    elif confidence > existing.confidence:
        # A later, cleaner filing (e.g. the audited version) supersedes.
        existing.revenue = current.get("revenue")
        existing.ebitda = current.get("ebitda")
        existing.pbt = current.get("pbt")
        existing.pat = current.get("pat")
        existing.confidence = confidence
    session.flush()


async def extract_person(announcement: Announcement) -> dict[str, Any] | None:
    """Who is arriving or leaving, and where did they come from."""
    payload = await get_llm().complete_json(
        stage="person_enrichment",
        system=enrich_prompts.PERSON_SYSTEM,
        prompt=enrich_prompts.build_person_prompt(announcement.subject, announcement.body),
        tier="cheap",
        max_tokens=400,
    )
    if not isinstance(payload, dict) or not payload.get("name"):
        return None
    return {
        "type": "person",
        "name": payload.get("name"),
        "role": payload.get("role"),
        "direction": payload.get("direction") or "unclear",
        "effective": payload.get("effective"),
        "background": payload.get("background"),
        "tenure_note": payload.get("tenure_note"),
    }


async def enrich(
    session: Session, company: Company, announcement: Announcement, document_text: str = ""
) -> dict[str, Any] | None:
    """Route a filing to its rich renderer, if it has one."""
    if announcement.category == Category.RESULTS:
        return await extract_results(session, company, announcement, document_text)
    if announcement.category == Category.MANAGEMENT_CHANGE:
        return await extract_person(announcement)
    return None
