"""Primary-source documents: annual reports and concall transcripts.

screener.in consolidates both as outbound links on the company page. We scrape
the links, not the numbers — the numbers come from the documents themselves,
because the brief requires analysis grounded in primary sources.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Company, Document
from app.services.ingest import seed
from app.utils.http import SessionClient
from app.utils.pdf import extract_text
from app.utils.text import content_hash

log = get_logger(__name__)

SCREENER_BASE = "https://www.screener.in"

_FY_RE = re.compile(r"(?:fy\s*|20)(\d{2})", re.I)
_Q_RE = re.compile(r"\bq([1-4])\b", re.I)


@dataclass(slots=True)
class DocumentLink:
    kind: str
    title: str
    url: str
    fiscal_year: int | None = None
    quarter: int | None = None


def _infer_period(title: str) -> tuple[int | None, int | None]:
    """Pull FY and quarter out of a link label like 'Q2 FY2027 Transcript'."""
    fy_match = _FY_RE.search(title)
    q_match = _Q_RE.search(title)
    fy = None
    if fy_match:
        two_digit = int(fy_match.group(1))
        fy = 2000 + two_digit if two_digit < 90 else 1900 + two_digit
    return fy, int(q_match.group(1)) if q_match else None


def parse_screener_html(html: str) -> list[DocumentLink]:
    """Extract document links from a screener company page.

    Written defensively: screener's markup changes, so we key on link text and
    href shape rather than on a specific DOM path, and return [] rather than
    raising if nothing matches.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:  # pragma: no cover
        return []

    links: list[DocumentLink] = []
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:  # noqa: BLE001
        return []

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        label = " ".join(anchor.get_text(" ", strip=True).split())
        if not href.startswith("http") or not label:
            continue
        lowered = label.lower()
        blob = f"{lowered} {href.lower()}"
        if "transcript" in blob:
            kind = "transcript"
        elif "annual report" in blob or "annualreport" in blob:
            kind = "annual_report"
        elif "ppt" in lowered or "presentation" in blob:
            kind = "presentation"
        else:
            continue
        fy, quarter = _infer_period(label)
        links.append(DocumentLink(kind, label[:240], href, fy, quarter))

    # De-duplicate on URL while preserving document order.
    seen: set[str] = set()
    unique: list[DocumentLink] = []
    for link in links:
        if link.url in seen:
            continue
        seen.add(link.url)
        unique.append(link)
    return unique


async def discover_documents(symbol: str, slug: str | None = None) -> list[DocumentLink]:
    if not settings.allow_network:
        return _seeded_links(symbol)
    path = f"/company/{slug or symbol}/consolidated/"
    try:
        async with SessionClient(SCREENER_BASE) as client:
            html = (await client.get_bytes(f"{SCREENER_BASE}{path}")).decode("utf-8", "ignore")
        links = parse_screener_html(html)
        if links:
            return links
        log.info("no documents parsed for %s; trying standalone page", symbol)
    except Exception as exc:  # noqa: BLE001
        log.warning("screener lookup failed for %s: %s", symbol, exc)
    return _seeded_links(symbol) if settings.use_seed_fallback else []


def _seeded_links(symbol: str) -> list[DocumentLink]:
    entry: dict[str, Any] = seed.seeded_fundamentals().get(symbol, {})
    return [
        DocumentLink(
            kind=d.get("kind", "transcript"),
            title=d.get("title", ""),
            url=d.get("url", ""),
            fiscal_year=d.get("fiscal_year"),
            quarter=d.get("quarter"),
        )
        for d in entry.get("documents", [])
    ]


def record_documents(session: Session, company: Company, links: list[DocumentLink]) -> int:
    created = 0
    for link in links:
        url_hash = content_hash(link.url)
        exists = session.scalars(
            select(Document).where(Document.url_hash == url_hash)
        ).first()
        if exists:
            continue
        session.add(
            Document(
                company_id=company.id,
                kind=link.kind,
                title=link.title,
                url=link.url,
                url_hash=url_hash,
                fiscal_year=link.fiscal_year,
                quarter=link.quarter,
            )
        )
        created += 1
    session.flush()
    return created


async def load_document_text(document: Document) -> str:
    """Download and extract one document, with the seeded text as fallback.

    Returns '' for an unreachable or image-only document. Callers treat that
    as 'no primary data' — never as an error worth surfacing to the user.
    """
    seeded = seed.seeded_fundamentals()
    for entry in seeded.values():
        for doc in entry.get("documents", []):
            if doc.get("url") == document.url and doc.get("text"):
                return doc["text"]

    if not settings.allow_network or not document.url:
        return ""
    try:
        async with SessionClient(SCREENER_BASE) as client:
            payload = await client.get_bytes(document.url)
    except Exception as exc:  # noqa: BLE001
        log.warning("could not download %s: %s", document.url, exc)
        return ""

    if document.url.lower().endswith(".pdf") or payload[:4] == b"%PDF":
        return extract_text(payload, source=document.url)
    return payload.decode("utf-8", "ignore")
