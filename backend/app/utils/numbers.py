"""Numeric helpers for financial data.

Filings report in lakhs, crores or millions and occasionally in parentheses
for negatives. Everything here returns a float in **crore** or None, never
raises, and never silently turns a parse failure into a zero.
"""
from __future__ import annotations

import math
import re

_UNIT_TO_CRORE = {
    "crore": 1.0,
    "cr": 1.0,
    "lakh": 0.01,
    "lac": 0.01,
    "million": 0.1,
    "mn": 0.1,
    "billion": 100.0,
    "bn": 100.0,
    "thousand": 0.0001,
}

_NUM_RE = re.compile(r"^\(?\s*-?\s*[\d,]+(?:\.\d+)?\s*\)?$")


def parse_amount(raw: object, unit: str | None = None) -> float | None:
    """Parse a reported figure into crore. Returns None on anything unclear."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        value = float(raw)
        if math.isnan(value) or math.isinf(value):
            return None
    else:
        text = str(raw).strip()
        if not text or text in {"-", "—", "NA", "N/A", "nil", "Nil"}:
            return None
        negative = text.startswith("(") and text.endswith(")")
        cleaned = text.strip("()").replace(",", "").replace("₹", "").replace("Rs.", "")
        cleaned = cleaned.replace("Rs", "").strip()
        inline_unit = None
        for token, factor in _UNIT_TO_CRORE.items():
            if re.search(rf"\b{token}s?\b", cleaned, re.I):
                inline_unit = factor
                cleaned = re.sub(rf"\b{token}s?\b", "", cleaned, flags=re.I).strip()
                break
        if not _NUM_RE.match(cleaned):
            return None
        try:
            value = float(cleaned)
        except ValueError:
            return None
        if negative:
            value = -value
        if inline_unit is not None:
            return round(value * inline_unit, 4)

    factor = _UNIT_TO_CRORE.get((unit or "crore").strip().lower(), 1.0)
    return round(value * factor, 4)


def pct_change(current: float | None, base: float | None) -> float | None:
    """Percentage change, guarded for the cases that actually occur.

    A sign flip (loss -> profit) has no meaningful percentage, and division by
    a near-zero base produces a number that is technically correct and
    practically a lie. Both return None so the UI can say 'n.m.' instead.
    """
    if current is None or base is None:
        return None
    if abs(base) < 1e-6:
        return None
    if base < 0 < current or current < 0 < base:
        return None
    return round((current - base) / abs(base) * 100.0, 1)


def safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or abs(denominator) < 1e-9:
        return None
    return round(numerator / denominator, 4)


def margin_pct(profit: float | None, revenue: float | None) -> float | None:
    ratio = safe_ratio(profit, revenue)
    return None if ratio is None else round(ratio * 100.0, 2)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
