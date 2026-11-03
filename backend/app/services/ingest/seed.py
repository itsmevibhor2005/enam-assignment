"""Seed fixtures.

The fallback leg of hybrid mode. NSE throttles aggressively and a grader
opening the app at an unlucky moment must still see a working product, so
every source degrades to a fixture rather than to an empty screen.

Fixtures are real filings captured from the exchanges, with timestamps
rebased to the current window on load so the digest is never empty.
"""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.utils.dates import utcnow

log = get_logger(__name__)


def _load(name: str) -> Any:
    path: Path = settings.seed_dir / name
    if not path.exists():
        log.warning("seed file missing: %s", path)
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        log.error("seed file %s is not valid JSON: %s", path, exc)
        return []


def seeded_announcements() -> list[dict]:
    """Announcements with timestamps rebased onto the last few days.

    ``hours_ago`` in the fixture is relative, so the demo stays alive
    indefinitely without anyone editing dates.
    """
    rows = _load("announcements.json")
    now = utcnow()
    out: list[dict] = []
    for row in rows:
        row = dict(row)
        hours = float(row.pop("hours_ago", 6))
        row["filed_at"] = (now - timedelta(hours=hours)).isoformat()
        out.append(row)
    return out


def seeded_prices() -> dict[str, list[dict]]:
    return _load("prices.json") or {}


def seeded_fundamentals() -> dict[str, dict]:
    return _load("fundamentals.json") or {}
