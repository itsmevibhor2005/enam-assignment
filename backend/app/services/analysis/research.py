"""Pull-side orchestration: snapshot, trajectory and bull/bear.

Generalises to any NSE symbol. An unknown ticker is created on demand, its
documents discovered, and the pipeline run live — which is why the API
exposes this as a staged operation the UI can narrate instead of a spinner.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import InsufficientData
from app.core.logging import get_logger
from app.db.models import Company, Document
from app.llm.client import get_llm
from app.llm.prompts import analysis as prompts
from app.services.ingest.fundamentals import (
    discover_documents,
    load_document_text,
    record_documents,
)
from app.utils.text import truncate

log = get_logger(__name__)


@dataclass(slots=True)
class ResearchBundle:
    symbol: str
    name: str
    snapshot: dict[str, Any] | None = None
    bull_bear: dict[str, list[str]] | None = None
    sources: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


async def resolve_company(session: Session, symbol: str) -> Company:
    """Find or create a company record for an arbitrary ticker.

    The brief says they may point this at a company we did not pick, so an
    unknown symbol is a normal path, not an error.
    """
    symbol = symbol.strip().upper()
    if not symbol or not symbol.replace("&", "").replace("-", "").isalnum():
        raise InsufficientData("That does not look like an NSE symbol.")

    company = session.scalars(select(Company).where(Company.symbol == symbol)).first()
    if company:
        return company

    company = Company(
        symbol=symbol,
        name=symbol.title(),
        exchange="NSE",
        in_portfolio=False,
        market_cap_band="mid",
    )
    session.add(company)
    session.flush()
    log.info("created company record on demand: %s", symbol)
    return company


async def ensure_documents(session: Session, company: Company) -> list[Document]:
    documents = list(
        session.scalars(select(Document).where(Document.company_id == company.id))
    )
    if documents:
        return documents
    links = await discover_documents(company.symbol, company.screener_slug)
    if links:
        record_documents(session, company, links)
    return list(session.scalars(select(Document).where(Document.company_id == company.id)))


def _pick_primary(documents: list[Document]) -> Document | None:
    """Prefer the most recent annual report; fall back to a transcript."""
    reports = [d for d in documents if d.kind == "annual_report"]
    if reports:
        return sorted(reports, key=lambda d: d.fiscal_year or 0, reverse=True)[0]
    transcripts = sorted(
        [d for d in documents if d.kind == "transcript"],
        key=lambda d: (d.fiscal_year or 0, d.quarter or 0),
        reverse=True,
    )
    return transcripts[0] if transcripts else None


async def build_bundle(session: Session, company: Company) -> ResearchBundle:
    bundle = ResearchBundle(symbol=company.symbol, name=company.name)
    documents = await ensure_documents(session, company)

    if not documents:
        bundle.warnings.append(
            "No annual reports or transcripts found for this ticker on screener.in."
        )
        return bundle

    primary = _pick_primary(documents)
    if primary is None:
        bundle.warnings.append("Only presentations were available — not a primary source.")
        return bundle

    text = await load_document_text(primary)
    if not text:
        bundle.warnings.append(
            f"{truncate(primary.title, 60)} could not be read — it may be a scanned filing."
        )
        return bundle

    primary.extracted = True
    primary.char_count = len(text)
    bundle.sources.append({"title": primary.title, "url": primary.url, "kind": primary.kind})

    llm = get_llm()
    snapshot = await llm.complete_json(
        stage="business_snapshot",
        system=prompts.SNAPSHOT_SYSTEM,
        prompt=prompts.build_snapshot_prompt(company.name, text),
        tier="strong",
        max_tokens=2000,
    )
    if isinstance(snapshot, dict):
        bundle.snapshot = snapshot

    cases = await llm.complete_json(
        stage="bull_bear",
        system=prompts.BULL_BEAR_SYSTEM,
        prompt=prompts.build_bull_bear_prompt(company.name, text),
        tier="cheap",
        max_tokens=900,
    )
    if isinstance(cases, dict):
        bundle.bull_bear = {
            "bull": [str(x) for x in (cases.get("bull") or [])][:3],
            "bear": [str(x) for x in (cases.get("bear") or [])][:3],
        }

    if bundle.snapshot is None and bundle.bull_bear is None:
        bundle.warnings.append("The model returned nothing usable from the primary source.")
    return bundle
