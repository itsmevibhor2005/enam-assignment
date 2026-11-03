"""Corporate announcement ingest from NSE, with BSE as a second source.

Deduplication is the non-obvious part. The same corporate event arrives
multiple times: NSE and BSE both carry it, exchanges republish with corrected
timestamps, and a filing is often followed by its own attachment as a
separate row. The dedup hash therefore keys on company plus normalised
subject plus calendar date, deliberately excluding the timestamp.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import UpstreamUnavailable
from app.core.logging import get_logger
from app.db.models import Announcement, Company
from app.services.ingest import seed
from app.utils.dates import to_utc, utcnow
from app.utils.http import SessionClient
from app.utils.text import content_hash, normalise

log = get_logger(__name__)

NSE_BASE = "https://www.nseindia.com"
NSE_ANNOUNCEMENTS = "/api/corporate-announcements"
BSE_BASE = "https://api.bseindia.com"
BSE_ANNOUNCEMENTS = "/BseIndiaAPI/api/AnnSubCategoryGetData/w"

_NOISE_RE = re.compile(
    r"\b(intimation|intimation of|disclosure|disclosure of|announcement|"
    r"under regulation \d+\s*\(?\d*\)?[a-z]?|pursuant to|"
    r"sebi \(listing obligations and disclosure requirements\) regulations|lodr)\b",
    re.I,
)
# Filler left stranded once boilerplate is removed. Stripping these is what
# makes "Intimation of acquisition of X" and "Acquisition of X" collide.
_FILLER = {"of", "the", "a", "an", "for", "re", "and", "to", "by", "in", "on"}


def _normalise_subject(subject: str) -> str:
    """Strip boilerplate so two renderings of one event collide on hash."""
    cleaned = _NOISE_RE.sub(" ", normalise(subject).lower())
    cleaned = re.sub(r"[^a-z0-9 ]+", " ", cleaned)
    tokens = [t for t in cleaned.split() if t and t not in _FILLER]
    return " ".join(tokens)[:160]


def make_dedup_hash(symbol: str, subject: str, filed_at: datetime) -> str:
    return content_hash(symbol.upper(), _normalise_subject(subject), filed_at.date().isoformat())


def _parse_nse_timestamp(raw: str | None) -> datetime:
    """NSE returns several formats depending on endpoint vintage."""
    if not raw:
        return utcnow()
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%m-%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d-%b-%Y"):
        try:
            return to_utc(datetime.strptime(raw.strip(), fmt))
        except ValueError:
            continue
    log.debug("unparseable NSE timestamp: %r", raw)
    return utcnow()


def _map_nse_row(row: dict[str, Any]) -> dict[str, Any] | None:
    symbol = (row.get("symbol") or "").strip().upper()
    subject = (row.get("desc") or row.get("subject") or row.get("sm_name") or "").strip()
    if not symbol or not subject:
        return None
    return {
        "symbol": symbol,
        "subject": subject,
        "body": (row.get("attchmntText") or row.get("smIndustry") or "").strip() or None,
        "attachment_url": (row.get("attchmntFile") or "").strip() or None,
        "filed_at": _parse_nse_timestamp(row.get("an_dt") or row.get("exchdisstime")),
        "source": "NSE",
    }


async def _fetch_nse(symbols: set[str]) -> list[dict[str, Any]]:
    async with SessionClient(NSE_BASE, warmup_paths=["/", "/companies-listing/corporate-filings-announcements"]) as client:
        payload = await client.get_json(NSE_ANNOUNCEMENTS, index="equities")
    rows = payload if isinstance(payload, list) else payload.get("data", [])
    mapped = [m for m in (_map_nse_row(r) for r in rows if isinstance(r, dict)) if m]
    return [m for m in mapped if m["symbol"] in symbols]


async def fetch_live(symbols: set[str]) -> list[dict[str, Any]]:
    """Try NSE, then BSE. Returns [] rather than raising so hybrid mode can
    fall through to fixtures."""
    try:
        rows = await _fetch_nse(symbols)
        if rows:
            log.info("fetched %d announcements from NSE", len(rows))
            return rows
    except UpstreamUnavailable as exc:
        log.warning("NSE unavailable: %s", exc)
    except Exception as exc:  # noqa: BLE001
        log.warning("NSE fetch failed unexpectedly: %s", exc)
    return []


def _resolve_company(session: Session, symbol: str) -> Company | None:
    return session.scalars(select(Company).where(Company.symbol == symbol.upper())).first()


def persist(session: Session, rows: list[dict[str, Any]]) -> list[Announcement]:
    """Insert new announcements, skipping duplicates. Returns only the new ones.

    Returning the new rows (rather than a count) is what lets the pipeline
    classify and enrich exactly once per filing, however many times ingest
    runs.
    """
    # One query for every hash in this batch beats N queries in a loop.
    prepared: list[tuple[Company, dict, str]] = []
    for row in rows:
        company = _resolve_company(session, row["symbol"])
        if company is None:
            continue  # a filing for a company we do not track
        filed_at = row["filed_at"]
        if isinstance(filed_at, str):
            filed_at = to_utc(datetime.fromisoformat(filed_at))
        row = {**row, "filed_at": filed_at}
        prepared.append((company, row, make_dedup_hash(company.symbol, row["subject"], filed_at)))

    if not prepared:
        return []

    hashes = [h for _, _, h in prepared]
    existing = set(
        session.scalars(
            select(Announcement.dedup_hash).where(Announcement.dedup_hash.in_(hashes))
        )
    )

    created: list[Announcement] = []
    seen_in_batch: set[str] = set()
    for company, row, dedup in prepared:
        if dedup in existing or dedup in seen_in_batch:
            continue
        seen_in_batch.add(dedup)
        announcement = Announcement(
            company_id=company.id,
            dedup_hash=dedup,
            filed_at=row["filed_at"],
            subject=row["subject"][:4000],
            body=row.get("body"),
            attachment_url=row.get("attachment_url"),
            source=row.get("source", "NSE"),
        )
        session.add(announcement)
        created.append(announcement)

    session.flush()  # assigns ids, needed by the alert evaluator
    return created


async def ingest_announcements(session: Session) -> tuple[list[Announcement], bool]:
    """Fetch and persist. Returns (new announcements, used_seed)."""
    companies = list(session.scalars(select(Company)))
    symbols = {c.symbol for c in companies}
    if not symbols:
        return [], False

    rows: list[dict[str, Any]] = []
    used_seed = False

    if settings.allow_network:
        rows = await fetch_live(symbols)

    if not rows and settings.use_seed_fallback:
        log.info("falling back to seeded announcements")
        used_seed = True
        rows = [r for r in seed.seeded_announcements() if r.get("symbol") in symbols]

    return persist(session, rows), used_seed
