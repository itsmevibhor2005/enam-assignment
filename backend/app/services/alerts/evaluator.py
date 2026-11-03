"""Threshold evaluation.

Two families of trigger, both configurable by the user:

1. Market triggers — an end-of-day move or volume spike beyond their
   thresholds.
2. Category triggers — a filing of a type they subscribed to, above a minimum
   score.

Every event carries a fingerprint so re-running ingest does not re-alert. The
investor should see a thing once.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.db.models import AlertRule, Announcement, Company, PriceBar
from app.services.classification.taxonomy import label_for
from app.utils.numbers import clamp
from app.utils.text import content_hash


@dataclass(slots=True)
class CandidateAlert:
    company_id: int
    kind: str
    headline: str
    detail: str | None
    severity: float
    triggered_at: datetime
    fingerprint: str
    announcement_id: int | None = None


def _fingerprint(*parts: object) -> str:
    return content_hash(*parts)[:48]


def evaluate_price_bar(
    company: Company, bar: PriceBar, rule: AlertRule
) -> list[CandidateAlert]:
    """Market-side triggers for one company's closing bar."""
    alerts: list[CandidateAlert] = []
    triggered_at = datetime.combine(bar.trade_date, datetime.min.time()).astimezone()

    if bar.pct_change is not None and abs(bar.pct_change) >= rule.price_move_pct:
        direction = "up" if bar.pct_change > 0 else "down"
        # Severity scales past the threshold, so a 12% move on a 4% threshold
        # outranks a 4.1% one instead of both reading as "triggered".
        severity = clamp(abs(bar.pct_change) / (rule.price_move_pct * 3.0), 0.3, 1.0)
        alerts.append(
            CandidateAlert(
                company_id=company.id,
                kind="price",
                headline=f"{company.symbol} closed {direction} {abs(bar.pct_change):.1f}%",
                detail=f"Close {bar.close:,.2f}, threshold ±{rule.price_move_pct:g}%",
                severity=severity,
                triggered_at=triggered_at,
                fingerprint=_fingerprint("price", company.id, bar.trade_date),
            )
        )

    if bar.volume_ratio is not None and bar.volume_ratio >= rule.volume_multiple:
        severity = clamp(bar.volume_ratio / (rule.volume_multiple * 2.5), 0.3, 1.0)
        alerts.append(
            CandidateAlert(
                company_id=company.id,
                kind="volume",
                headline=f"{company.symbol} traded {bar.volume_ratio:.1f}x its usual volume",
                detail=f"{bar.volume:,.0f} shares against a 20-day average",
                severity=severity,
                triggered_at=triggered_at,
                fingerprint=_fingerprint("volume", company.id, bar.trade_date),
            )
        )
    return alerts


def evaluate_announcement(
    company: Company, announcement: Announcement, rule: AlertRule
) -> CandidateAlert | None:
    """Category-side trigger for one filing."""
    if announcement.category not in rule.category_list:
        return None
    if announcement.score < rule.min_score:
        return None
    headline = announcement.summary or announcement.subject
    return CandidateAlert(
        company_id=company.id,
        kind="category",
        headline=f"{company.symbol}: {label_for(announcement.category)}",
        detail=headline[:240],
        severity=clamp(announcement.score, 0.3, 1.0),
        triggered_at=announcement.filed_at,
        fingerprint=_fingerprint("category", announcement.dedup_hash),
        announcement_id=announcement.id,
    )
