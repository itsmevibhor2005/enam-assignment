"""Date/time helpers.

Everything investor-facing is in IST. Everything stored is tz-aware UTC.
Indian listed companies run an April-March fiscal year, so quarter maths is
not the calendar-quarter maths you get for free from pandas.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
MARKET_CLOSE_IST = time(15, 30)

# Fiscal quarter -> months covered. FY2027 Q1 == Apr-Jun 2026.
_FY_QUARTER_START_MONTH = {1: 4, 2: 7, 3: 10, 4: 1}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_utc(dt: datetime) -> datetime:
    """Normalise any datetime to tz-aware UTC, assuming IST if naive.

    Exchange feeds hand us naive local timestamps; assuming UTC there would
    shift every filing back by 5.5 hours and silently corrupt the digest
    window.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return dt.astimezone(timezone.utc)


def to_ist(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)


def window_start(hours: int, *, now: datetime | None = None) -> datetime:
    """Start of a lookback window, clamped to a sane range."""
    hours = max(1, min(int(hours), 24 * 90))
    return (now or utcnow()) - timedelta(hours=hours)


def hours_since(dt: datetime, *, now: datetime | None = None) -> float:
    delta = (now or utcnow()) - to_utc(dt)
    return max(0.0, delta.total_seconds() / 3600.0)


@dataclass(frozen=True, slots=True)
class FiscalQuarter:
    """An Indian fiscal quarter. fy=2027, q=1 means Apr-Jun 2026."""

    fy: int
    q: int

    def __post_init__(self) -> None:
        if self.q not in (1, 2, 3, 4):
            raise ValueError(f"quarter must be 1-4, got {self.q}")

    @property
    def label(self) -> str:
        return f"Q{self.q} FY{str(self.fy)[-2:]}"

    @property
    def start(self) -> datetime:
        month = _FY_QUARTER_START_MONTH[self.q]
        year = self.fy if self.q == 4 else self.fy - 1
        return datetime(year, month, 1, tzinfo=IST)

    def previous(self) -> "FiscalQuarter":
        """Immediately preceding quarter — the QoQ comparator."""
        if self.q == 1:
            return FiscalQuarter(self.fy - 1, 4)
        return FiscalQuarter(self.fy, self.q - 1)

    def year_ago(self) -> "FiscalQuarter":
        """Same quarter one year earlier — the YoY comparator."""
        return FiscalQuarter(self.fy - 1, self.q)

    def has_elapsed(self, *, now: datetime | None = None) -> bool:
        """True once the quarter is over. Guidance for a future quarter can
        only ever be adjudicated 'too early'."""
        end = self.start + timedelta(days=95)
        return (now or utcnow()) > end

    @classmethod
    def from_date(cls, dt: datetime) -> "FiscalQuarter":
        dt = to_ist(dt)
        if dt.month >= 4:
            return cls(dt.year + 1, (dt.month - 4) // 3 + 1)
        return cls(dt.year, 4 if dt.month <= 3 else 1)

    @classmethod
    def parse(cls, label: str) -> "FiscalQuarter | None":
        """Parse 'Q1 FY27', 'Q1FY2027', 'q3 fy26'. Returns None if unreadable
        rather than raising — model output is untrusted input."""
        import re

        m = re.search(r"q\s*([1-4])\s*,?\s*fy\s*(\d{2,4})", label.strip(), re.I)
        if not m:
            return None
        q, fy_raw = int(m.group(1)), m.group(2)
        fy = int(fy_raw) if len(fy_raw) == 4 else 2000 + int(fy_raw)
        return cls(fy, q)


def last_n_quarters(n: int, *, now: datetime | None = None) -> list[FiscalQuarter]:
    """The n most recently *reported* quarters, newest first.

    Results land roughly 4-6 weeks after quarter end, so the quarter we are
    currently inside has not been reported; we start from the one before.
    """
    current = FiscalQuarter.from_date(to_ist(now or utcnow()))
    cursor = current.previous()
    out: list[FiscalQuarter] = []
    for _ in range(max(1, n)):
        out.append(cursor)
        cursor = cursor.previous()
    return out
