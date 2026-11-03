"""The nightly pipeline.

    companies -> prices -> announcements -> classify -> score -> enrich -> alerts

Ordering is not arbitrary: scoring needs the day's price action to compute
market corroboration, so prices must land before announcements are scored,
and alerts run last because they read the finished scores.

The whole run is defensive. One company's unreachable PDF, one malformed
model response, or a dead exchange endpoint degrades that step only. A
half-filled digest is a working product; a crashed job at 7pm is not.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import AlertEvent, AlertRule, Announcement, Company, IngestRun, PriceBar
from app.db.session import session_scope
from app.services.alerts import evaluator
from app.services.analysis import enrichment
from app.services.classification.classifier import classify_batch
from app.services.classification.taxonomy import Category
from app.services.ingest import announcements as ann_ingest
from app.services.ingest import fundamentals, prices
from app.services.ingest.portfolio import all_holdings
from app.services.ranking.scorer import MarketContext, score_announcement
from app.utils.dates import hours_since, utcnow
from app.utils.pdf import extract_text

log = get_logger(__name__)

# Enrichment is the expensive step. Cap it per run so one busy results day
# cannot exhaust a free-tier daily quota.
_MAX_ENRICHMENTS_PER_RUN = 12


@dataclass
class RunSummary:
    prices: int = 0
    announcements: int = 0
    classified_by_rules: int = 0
    classified_by_model: int = 0
    enriched: int = 0
    alerts: int = 0
    used_seed: bool = False
    errors: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


def ensure_companies(session: Session) -> int:
    """Idempotent seeding of the tracked universe."""
    created = 0
    for holding, in_portfolio in all_holdings():
        existing = session.scalars(
            select(Company).where(Company.symbol == holding.symbol)
        ).first()
        if existing:
            existing.in_portfolio = in_portfolio
            continue
        session.add(
            Company(
                symbol=holding.symbol,
                name=holding.name,
                sector=holding.sector,
                market_cap_band=holding.band,
                screener_slug=holding.screener_slug,
                in_portfolio=in_portfolio,
                exchange="NSE",
            )
        )
        created += 1
    session.flush()
    return created


def get_rule(session: Session, profile: str = "default") -> AlertRule:
    rule = session.scalars(select(AlertRule).where(AlertRule.profile == profile)).first()
    if rule is None:
        rule = AlertRule(profile=profile)
        session.add(rule)
        session.flush()
    return rule


def _market_context(session: Session, company_id: int) -> MarketContext:
    bar = prices.latest_bar(session, company_id)
    if bar is None:
        return MarketContext()
    return MarketContext(pct_change=bar.pct_change, volume_ratio=bar.volume_ratio)


def score_pending(session: Session, items: list[Announcement]) -> None:
    """Attach a score to each announcement, using same-day market context."""
    companies = {c.id: c for c in session.scalars(select(Company))}
    contexts: dict[int, MarketContext] = {}

    for announcement in items:
        company = companies.get(announcement.company_id)
        if company is None:
            continue
        if company.id not in contexts:
            contexts[company.id] = _market_context(session, company.id)
        scored = score_announcement(
            category=announcement.category,
            materiality=announcement.materiality,
            hours_old=hours_since(announcement.filed_at),
            market=contexts[company.id],
            market_cap_band=company.market_cap_band,
            in_portfolio=company.in_portfolio,
        )
        announcement.score = scored.score
        announcement.is_routine = scored.is_routine
    session.flush()


async def enrich_pending(session: Session, items: list[Announcement]) -> int:
    """Summarise and richly render the items that earn it.

    Processed highest-score-first so that if the cap bites, it bites on the
    least important filings.
    """
    companies = {c.id: c for c in session.scalars(select(Company))}
    ranked = sorted(items, key=lambda a: a.score, reverse=True)[:_MAX_ENRICHMENTS_PER_RUN]
    count = 0

    for announcement in ranked:
        company = companies.get(announcement.company_id)
        if company is None:
            continue
        try:
            if announcement.summary is None:
                announcement.summary = await enrichment.summarise(announcement)

            document_text = ""
            if announcement.category == Category.RESULTS and announcement.attachment_url:
                document_text = await _load_attachment(announcement.attachment_url)

            payload = await enrichment.enrich(session, company, announcement, document_text)
            if payload:
                announcement.enrichment = payload
                count += 1
        except Exception as exc:  # noqa: BLE001 - never abort the run
            log.warning("enrichment failed for %s: %s", announcement.subject[:60], exc)
    session.flush()
    return count


async def _load_attachment(url: str) -> str:
    from app.core.config import settings
    from app.utils.http import SessionClient

    if not settings.allow_network:
        return ""
    try:
        async with SessionClient("https://www.nseindia.com") as client:
            payload = await client.get_bytes(url)
        return extract_text(payload, source=url)
    except Exception as exc:  # noqa: BLE001
        log.info("could not load attachment %s: %s", url, exc)
        return ""


def fire_alerts(session: Session, new_announcements: list[Announcement]) -> int:
    """Evaluate both trigger families and persist anything not already seen."""
    rule = get_rule(session)
    if not rule.enabled:
        return 0

    companies = {c.id: c for c in session.scalars(select(Company))}
    candidates: list[evaluator.CandidateAlert] = []

    for company in companies.values():
        if not company.in_portfolio:
            continue  # market alerts are a portfolio concern
        bar = prices.latest_bar(session, company.id)
        if bar:
            candidates.extend(evaluator.evaluate_price_bar(company, bar, rule))

    for announcement in new_announcements:
        company = companies.get(announcement.company_id)
        if company is None:
            continue
        candidate = evaluator.evaluate_announcement(company, announcement, rule)
        if candidate:
            candidates.append(candidate)

    if not candidates:
        return 0

    fingerprints = [c.fingerprint for c in candidates]
    existing = set(
        session.scalars(
            select(AlertEvent.fingerprint).where(AlertEvent.fingerprint.in_(fingerprints))
        )
    )

    fired = 0
    for candidate in candidates:
        if candidate.fingerprint in existing:
            continue
        existing.add(candidate.fingerprint)
        session.add(AlertEvent(**asdict(candidate)))
        fired += 1
    session.flush()
    return fired


async def run_ingest(*, discover_fundamentals: bool = False) -> RunSummary:
    """Execute one full pipeline pass."""
    summary = RunSummary()

    with session_scope() as session:
        run = IngestRun(started_at=utcnow())
        session.add(run)
        session.flush()

        try:
            ensure_companies(session)

            try:
                summary.prices, seeded_prices = prices.ingest_prices(session)
                summary.used_seed |= seeded_prices
            except Exception as exc:  # noqa: BLE001
                summary.errors.append(f"prices: {exc}")
                log.exception("price ingest failed")

            new_items: list[Announcement] = []
            try:
                new_items, seeded_ann = await ann_ingest.ingest_announcements(session)
                summary.announcements = len(new_items)
                summary.used_seed |= seeded_ann
            except Exception as exc:  # noqa: BLE001
                summary.errors.append(f"announcements: {exc}")
                log.exception("announcement ingest failed")

            if new_items:
                companies = {c.id: c for c in session.scalars(select(Company))}
                try:
                    stats = await classify_batch(session, new_items, companies)
                    summary.classified_by_rules = stats.by_rules
                    summary.classified_by_model = stats.by_model
                except Exception as exc:  # noqa: BLE001
                    summary.errors.append(f"classification: {exc}")

                score_pending(session, new_items)

                try:
                    summary.enriched = await enrich_pending(session, new_items)
                except Exception as exc:  # noqa: BLE001
                    summary.errors.append(f"enrichment: {exc}")

            # Rescore everything still inside the longest digest window, so
            # recency decay stays accurate between runs.
            _rescore_recent(session)

            try:
                summary.alerts = fire_alerts(session, new_items)
            except Exception as exc:  # noqa: BLE001
                summary.errors.append(f"alerts: {exc}")

            if discover_fundamentals:
                await _discover_all_documents(session)

            run.status = "ok" if not summary.errors else "partial"
        except Exception as exc:  # noqa: BLE001
            run.status = "failed"
            summary.errors.append(str(exc))
            log.exception("ingest run failed")
        finally:
            run.finished_at = utcnow()
            run.prices_ingested = summary.prices
            run.announcements_ingested = summary.announcements
            run.alerts_fired = summary.alerts
            run.fell_back_to_seed = summary.used_seed
            run.notes = "; ".join(summary.errors)[:2000] or None

    return summary


def _rescore_recent(session: Session, days: int = 30) -> None:
    from datetime import timedelta

    cutoff = utcnow() - timedelta(days=days)
    recent = list(
        session.scalars(select(Announcement).where(Announcement.filed_at >= cutoff))
    )
    if recent:
        score_pending(session, recent)


async def _discover_all_documents(session: Session) -> None:
    """Populate document links for every tracked company. Slow, so it runs
    only when explicitly asked for."""
    companies = list(session.scalars(select(Company)))
    for company in companies:
        try:
            links = await fundamentals.discover_documents(
                company.symbol, company.screener_slug
            )
            if links:
                fundamentals.record_documents(session, company, links)
        except Exception as exc:  # noqa: BLE001
            log.info("document discovery failed for %s: %s", company.symbol, exc)
        await asyncio.sleep(0.5)  # be polite to screener
