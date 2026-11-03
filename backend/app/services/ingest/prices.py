"""End-of-day price and volume ingest.

Derived fields are computed here, once, rather than in the alert evaluator or
the API. Two subtleties that matter:

* The trailing volume average **excludes the current bar**. Including it
  damps exactly the spike we are trying to detect.
* yfinance returns split- and bonus-adjusted closes. Without that, a 1:2
  split reads as a -50% day and fires a price alert on a non-event.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Company, PriceBar
from app.services.ingest import seed
from app.utils.numbers import pct_change

log = get_logger(__name__)

_VOLUME_LOOKBACK = 20
_MIN_BARS_FOR_RATIO = 5


def _compute_derived(bars: list[dict]) -> list[dict]:
    """Attach pct_change and volume_ratio to a chronological list of bars."""
    out: list[dict] = []
    for index, bar in enumerate(bars):
        prev_close = bars[index - 1]["close"] if index > 0 else None
        window = bars[max(0, index - _VOLUME_LOOKBACK) : index]  # excludes self
        volumes = [b["volume"] for b in window if b.get("volume")]

        ratio = None
        if len(volumes) >= _MIN_BARS_FOR_RATIO:
            average = sum(volumes) / len(volumes)
            if average > 0:
                ratio = round(bar["volume"] / average, 3)

        out.append(
            {
                **bar,
                "pct_change": pct_change(bar["close"], prev_close),
                "volume_ratio": ratio,
            }
        )
    return out


def _fetch_live(tickers: list[str], lookback_days: int) -> dict[str, list[dict]]:
    """Pull EOD bars from Yahoo. Returns {} on any failure so the caller can
    fall back rather than abort the whole ingest run."""
    try:
        import yfinance as yf
    except ImportError:  # pragma: no cover
        log.warning("yfinance not installed")
        return {}

    try:
        frame = yf.download(
            tickers=" ".join(tickers),
            period=f"{lookback_days}d",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,      # split/bonus adjusted — see module docstring
            progress=False,
            threads=True,
        )
    except Exception as exc:  # noqa: BLE001 - yfinance raises many things
        log.warning("yfinance download failed: %s", exc)
        return {}

    if frame is None or frame.empty:
        return {}

    result: dict[str, list[dict]] = {}
    for ticker in tickers:
        try:
            sub = frame[ticker] if len(tickers) > 1 else frame
        except (KeyError, TypeError):
            continue
        sub = sub.dropna(subset=["Close"])
        bars = [
            {
                "trade_date": idx.date() if hasattr(idx, "date") else idx,
                "close": float(row["Close"]),
                "volume": float(row.get("Volume") or 0.0),
            }
            for idx, row in sub.iterrows()
        ]
        if bars:
            result[ticker] = bars
    return result


def ingest_prices(session: Session, *, lookback_days: int = 60) -> tuple[int, bool]:
    """Upsert price bars for every tracked company.

    Returns (rows written, whether seed fallback was used).
    """
    companies = list(session.scalars(select(Company)))
    if not companies:
        return 0, False

    by_ticker = {c.yahoo_ticker: c for c in companies}
    fetched: dict[str, list[dict]] = {}
    used_seed = False

    if settings.allow_network:
        fetched = _fetch_live(list(by_ticker), lookback_days)

    if not fetched and settings.use_seed_fallback:
        log.info("falling back to seeded prices")
        used_seed = True
        seeded = seed.seeded_prices()
        for company in companies:
            rows = seeded.get(company.symbol)
            if rows:
                fetched[company.yahoo_ticker] = [
                    {
                        "trade_date": date.fromisoformat(r["trade_date"]),
                        "close": float(r["close"]),
                        "volume": float(r["volume"]),
                    }
                    for r in rows
                ]

    written = 0
    for ticker, bars in fetched.items():
        company = by_ticker.get(ticker)
        if not company or not bars:
            continue
        bars = sorted(bars, key=lambda b: b["trade_date"])
        enriched = _compute_derived(bars)

        existing = {
            row.trade_date: row
            for row in session.scalars(
                select(PriceBar).where(PriceBar.company_id == company.id)
            )
        }
        for bar in enriched:
            row = existing.get(bar["trade_date"])
            if row is None:
                session.add(PriceBar(company_id=company.id, **bar))
                written += 1
            else:
                # Backfill derived fields if an earlier partial run left them
                # null; never duplicate the row.
                row.close = bar["close"]
                row.volume = bar["volume"]
                row.pct_change = bar["pct_change"]
                row.volume_ratio = bar["volume_ratio"]
    session.flush()
    return written, used_seed


def latest_bar(session: Session, company_id: int) -> PriceBar | None:
    return session.scalars(
        select(PriceBar)
        .where(PriceBar.company_id == company_id)
        .order_by(PriceBar.trade_date.desc())
        .limit(1)
    ).first()


def bars_since(session: Session, company_id: int, days: int) -> list[PriceBar]:
    cutoff = date.today() - timedelta(days=days)
    return list(
        session.scalars(
            select(PriceBar)
            .where(PriceBar.company_id == company_id, PriceBar.trade_date >= cutoff)
            .order_by(PriceBar.trade_date.asc())
        )
    )
