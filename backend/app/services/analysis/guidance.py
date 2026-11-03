"""Promised vs delivered — the centrepiece of the pull side.

Two passes, deliberately separated:

1. EXTRACT: read each quarter's transcript and pull out checkable
   commitments. Cheap-to-mid tier, heavily prefiltered.
2. ADJUDICATE: compare each commitment against what the company actually
   reported in the quarters that followed. Strong tier — this is the only
   genuinely hard reasoning in the application.

Keeping them apart matters because extraction is stable (a transcript never
changes) and adjudication is not (a claim's verdict moves from too_early to
met as later quarters report). Extraction caches forever; adjudication
re-runs.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import Company, Document, GuidanceClaim, GuidanceOutcome, QuarterlyResult
from app.llm.client import get_llm
from app.llm.prompts import analysis as prompts
from app.services.ingest.fundamentals import load_document_text
from app.utils.dates import FiscalQuarter, utcnow
from app.utils.numbers import margin_pct
from app.utils.text import chunk_text, keyword_prefilter, truncate

log = get_logger(__name__)

# Guidance language is formulaic. This prefilter typically discards 60-75% of
# a transcript before any token reaches a model.
_GUIDANCE_KEYWORDS = [
    "guidance", "guide", "expect", "outlook", "target", "aspire", "we believe",
    "going forward", "next quarter", "next year", "full year", "fy2", "fy 2",
    "margin", "growth", "capex", "capacity", "order book", "run rate",
    "double digit", "single digit", "basis points", "bps", "trajectory",
]

_VALID_STATUSES = {"met", "missed", "partial", "too_early", "unverifiable"}

# Metric name -> how to compute the actual from a QuarterlyResult.
_METRIC_RESOLVERS: dict[str, str] = {
    "revenue": "revenue",
    "revenue growth": "revenue",
    "sales": "revenue",
    "ebitda": "ebitda",
    "ebitda margin": "ebitda_margin",
    "operating margin": "ebitda_margin",
    "margin": "ebitda_margin",
    "pat": "pat",
    "profit": "pat",
    "pat margin": "pat_margin",
    "net margin": "pat_margin",
    "pbt": "pbt",
}


@dataclass(slots=True)
class ClaimRecord:
    claim: GuidanceClaim
    outcome: GuidanceOutcome | None = None


@dataclass(slots=True)
class GuidanceReport:
    company: str
    quarters_covered: list[str] = field(default_factory=list)
    records: list[ClaimRecord] = field(default_factory=list)
    scorecard: dict[str, int] = field(default_factory=dict)
    note: str | None = None


# --------------------------------------------------------------------------
# Pass 1 — extraction
# --------------------------------------------------------------------------

async def extract_claims(
    session: Session, company: Company, document: Document, text: str
) -> list[GuidanceClaim]:
    """Extract checkable commitments from one transcript."""
    if not text.strip():
        return []

    period = _document_period(document)
    chunks = keyword_prefilter(chunk_text(text, size=14_000, overlap=900), _GUIDANCE_KEYWORDS)
    if not chunks:
        return []

    # Opening remarks carry most guidance; cap the chunk count so one
    # 90-page transcript cannot consume an entire free-tier daily quota.
    chunks = chunks[:6]
    llm = get_llm()
    collected: list[dict] = []

    for index, chunk in enumerate(chunks):
        payload = await llm.complete_json(
            stage="guidance_extraction",
            system=prompts.GUIDANCE_SYSTEM,
            prompt=prompts.build_guidance_prompt(company.name, period.label, chunk),
            tier="cheap",
            max_tokens=2000,
        )
        if isinstance(payload, dict) and isinstance(payload.get("claims"), list):
            collected.extend(c for c in payload["claims"] if isinstance(c, dict))
        elif isinstance(payload, list):
            collected.extend(c for c in payload if isinstance(c, dict))

    return _persist_claims(session, company, document, period, collected)


def _document_period(document: Document) -> FiscalQuarter:
    if document.fiscal_year and document.quarter:
        return FiscalQuarter(document.fiscal_year, document.quarter)
    parsed = FiscalQuarter.parse(document.title or "")
    return parsed or FiscalQuarter.from_date(utcnow()).previous()


def _persist_claims(
    session: Session,
    company: Company,
    document: Document,
    period: FiscalQuarter,
    raw_claims: list[dict],
) -> list[GuidanceClaim]:
    """Validate, deduplicate and store. Model output is untrusted input."""
    existing_quotes = {
        c.quote.lower()[:80]
        for c in session.scalars(
            select(GuidanceClaim).where(
                GuidanceClaim.company_id == company.id,
                GuidanceClaim.said_fy == period.fy,
                GuidanceClaim.said_q == period.q,
            )
        )
    }

    created: list[GuidanceClaim] = []
    for raw in raw_claims:
        metric = (raw.get("metric") or "").strip()
        quote = (raw.get("quote") or "").strip()
        if not metric or not quote:
            continue

        low, high = _coerce_range(raw.get("target_low"), raw.get("target_high"))
        direction = _coerce_direction(raw.get("direction"))
        # A claim with neither a number nor a direction is not checkable; the
        # prompt forbids it, but the prompt is not a guarantee.
        if low is None and high is None and direction is None:
            continue

        key = quote.lower()[:80]
        if key in existing_quotes:
            continue
        existing_quotes.add(key)

        horizon = FiscalQuarter.parse(str(raw.get("horizon") or ""))
        claim = GuidanceClaim(
            company_id=company.id,
            document_id=document.id,
            said_fy=period.fy,
            said_q=period.q,
            metric=metric[:64],
            direction=direction,
            target_low=low,
            target_high=high,
            unit=_coerce_unit(raw.get("unit")),
            horizon_fy=horizon.fy if horizon else None,
            horizon_q=horizon.q if horizon else None,
            speaker=truncate(str(raw.get("speaker") or ""), 96) or None,
            quote=truncate(quote, 400),
        )
        session.add(claim)
        created.append(claim)

    session.flush()
    return created


def _coerce_range(low: Any, high: Any) -> tuple[float | None, float | None]:
    def num(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    lo, hi = num(low), num(high)
    if lo is not None and hi is not None and lo > hi:
        lo, hi = hi, lo  # model occasionally inverts a range
    return lo, hi


def _coerce_direction(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    return value if value in {"grow", "contract", "expand", "flat"} else None


def _coerce_unit(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    return value if value in {"pct", "crore", "x"} else None


# --------------------------------------------------------------------------
# Pass 2 — adjudication
# --------------------------------------------------------------------------

def _actuals_for(session: Session, company: Company, quarters: list[FiscalQuarter]) -> list[dict]:
    """Reported figures the adjudicator is allowed to reason from."""
    rows = session.scalars(
        select(QuarterlyResult).where(QuarterlyResult.company_id == company.id)
    ).all()
    wanted = {(q.fy, q.q) for q in quarters}
    out: list[dict] = []
    for row in rows:
        if (row.fiscal_year, row.quarter) not in wanted:
            continue
        out.append(
            {
                "period": row.label,
                "revenue": row.revenue,
                "ebitda": row.ebitda,
                "pbt": row.pbt,
                "pat": row.pat,
                "ebitda_margin_pct": margin_pct(row.ebitda, row.revenue),
                "pat_margin_pct": margin_pct(row.pat, row.revenue),
            }
        )
    return sorted(out, key=lambda r: r["period"])


def _horizon_elapsed(claim: GuidanceClaim) -> bool:
    """A claim about an unfinished period can only be 'too early'.

    Enforced in code rather than trusted to the model, because this is the
    one verdict error that would make the product actively misleading.
    """
    if claim.horizon_fy is None:
        return True  # no stated horizon; judge on what has reported
    quarter = FiscalQuarter(claim.horizon_fy, claim.horizon_q or 4)
    return quarter.has_elapsed()


async def adjudicate(
    session: Session, company: Company, claims: list[GuidanceClaim]
) -> dict[int, GuidanceOutcome]:
    """Judge each claim against reported figures."""
    if not claims:
        return {}

    judged = [c for c in claims if _horizon_elapsed(c)]
    pending = [c for c in claims if c not in judged]
    outcomes: dict[int, GuidanceOutcome] = {}

    assessed = FiscalQuarter.from_date(utcnow()).previous()
    for claim in pending:
        outcomes[claim.id] = _upsert_outcome(
            session,
            claim,
            assessed,
            status="too_early",
            actual=None,
            reasoning="Guidance period has not finished reporting yet.",
            confidence=1.0,
        )

    if not judged:
        session.flush()
        return outcomes

    horizons = [
        FiscalQuarter(c.horizon_fy, c.horizon_q or 4)
        for c in judged
        if c.horizon_fy is not None
    ]
    lookup_quarters = horizons or [assessed, assessed.previous(), assessed.previous().previous()]
    actuals = _actuals_for(session, company, lookup_quarters + [assessed, assessed.previous()])

    if not actuals:
        for claim in judged:
            outcomes[claim.id] = _upsert_outcome(
                session, claim, assessed,
                status="unverifiable",
                actual=None,
                reasoning="No reported figures available for the guided period.",
                confidence=0.9,
            )
        session.flush()
        return outcomes

    claims_payload = [
        {
            "claim_id": c.id,
            "said_in": f"Q{c.said_q} FY{str(c.said_fy)[-2:]}",
            "metric": c.metric,
            "direction": c.direction,
            "target_low": c.target_low,
            "target_high": c.target_high,
            "unit": c.unit,
            "horizon": (
                f"Q{c.horizon_q or 4} FY{str(c.horizon_fy)[-2:]}" if c.horizon_fy else None
            ),
            "quote": c.quote,
        }
        for c in judged
    ]

    payload = await get_llm().complete_json(
        stage="guidance_adjudication",
        system=prompts.ADJUDICATE_SYSTEM,
        prompt=prompts.build_adjudicate_prompt(
            company.name,
            json.dumps(claims_payload, ensure_ascii=False, indent=1),
            json.dumps(actuals, ensure_ascii=False, indent=1),
        ),
        tier="strong",
        max_tokens=2500,
    )

    verdicts = []
    if isinstance(payload, dict):
        verdicts = payload.get("verdicts") or []
    elif isinstance(payload, list):
        verdicts = payload

    by_id = {c.id: c for c in judged}
    seen: set[int] = set()
    for verdict in verdicts:
        if not isinstance(verdict, dict):
            continue
        claim = by_id.get(_as_int(verdict.get("claim_id")))
        if claim is None:
            continue
        status = str(verdict.get("status") or "").strip().lower()
        if status not in _VALID_STATUSES:
            status = "unverifiable"
        seen.add(claim.id)
        outcomes[claim.id] = _upsert_outcome(
            session,
            claim,
            assessed,
            status=status,
            actual=_as_float(verdict.get("actual_value")),
            reasoning=truncate(str(verdict.get("reasoning") or ""), 300)
            or "No reasoning returned.",
            confidence=_as_float(verdict.get("confidence")) or 0.5,
        )

    # A claim the model silently dropped must not vanish from the UI.
    for claim in judged:
        if claim.id not in seen:
            outcomes[claim.id] = _upsert_outcome(
                session, claim, assessed,
                status="unverifiable",
                actual=None,
                reasoning="Could not be matched against reported figures.",
                confidence=0.4,
            )

    session.flush()
    return outcomes


def _upsert_outcome(
    session: Session,
    claim: GuidanceClaim,
    assessed: FiscalQuarter,
    *,
    status: str,
    actual: float | None,
    reasoning: str,
    confidence: float,
) -> GuidanceOutcome:
    existing = session.scalars(
        select(GuidanceOutcome).where(
            GuidanceOutcome.claim_id == claim.id,
            GuidanceOutcome.assessed_fy == assessed.fy,
            GuidanceOutcome.assessed_q == assessed.q,
        )
    ).first()
    if existing:
        existing.status = status
        existing.actual_value = actual
        existing.reasoning = reasoning
        existing.confidence = confidence
        return existing
    outcome = GuidanceOutcome(
        claim_id=claim.id,
        assessed_fy=assessed.fy,
        assessed_q=assessed.q,
        status=status,
        actual_value=actual,
        reasoning=reasoning,
        confidence=confidence,
    )
    session.add(outcome)
    return outcome


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

async def build_report(
    session: Session, company: Company, *, quarters: int = 4
) -> GuidanceReport:
    """Full promised-vs-delivered report for a company.

    Reuses stored claims where the transcript has already been read, so a
    second visit to the same company costs nothing.
    """
    report = GuidanceReport(company=company.name)

    transcripts = list(
        session.scalars(
            select(Document)
            .where(Document.company_id == company.id, Document.kind == "transcript")
            .order_by(Document.fiscal_year.desc().nullslast(), Document.quarter.desc().nullslast())
            .limit(quarters)
        )
    )
    if not transcripts:
        report.note = "No concall transcripts available for this company yet."
        return report

    all_claims: list[GuidanceClaim] = []
    for document in transcripts:
        period = _document_period(document)
        report.quarters_covered.append(period.label)

        stored = list(
            session.scalars(
                select(GuidanceClaim).where(
                    GuidanceClaim.company_id == company.id,
                    GuidanceClaim.said_fy == period.fy,
                    GuidanceClaim.said_q == period.q,
                )
            )
        )
        if stored:
            all_claims.extend(stored)
            continue

        text = await load_document_text(document)
        if not text:
            log.info("transcript %s unreadable for %s", document.title, company.symbol)
            continue
        document.extracted = True
        document.char_count = len(text)
        all_claims.extend(await extract_claims(session, company, document, text))

    if not all_claims:
        report.note = (
            "Transcripts were read but contained no checkable commitments — "
            "management spoke only in qualitative terms."
        )
        return report

    outcomes = await adjudicate(session, company, all_claims)
    report.records = [
        ClaimRecord(claim=c, outcome=outcomes.get(c.id)) for c in all_claims
    ]
    report.scorecard = _scorecard(report.records)
    return report


def _scorecard(records: list[ClaimRecord]) -> dict[str, int]:
    counts = {status: 0 for status in _VALID_STATUSES}
    for record in records:
        if record.outcome:
            counts[record.outcome.status] = counts.get(record.outcome.status, 0) + 1
    return counts
