"""ORM models.

Design notes worth knowing before changing anything here:

* ``Announcement.dedup_hash`` is unique. Exchanges republish the same filing
  under corrected timestamps and both NSE and BSE carry the same event, so
  without it the digest shows duplicates. The hash deliberately excludes the
  timestamp.
* Derived fields (category, score, summary) live on the row rather than being
  recomputed per request. The digest endpoint is then a single indexed query
  and renders instantly on a phone.
* ``GuidanceClaim`` and ``GuidanceOutcome`` are separate tables because one
  claim is adjudicated repeatedly as later quarters report.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Company(Base, TimestampMixin):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    sector: Mapped[Optional[str]] = mapped_column(String(128))
    exchange: Mapped[str] = mapped_column(String(8), default="NSE")
    market_cap_band: Mapped[Optional[str]] = mapped_column(String(16))  # large/mid/small
    in_portfolio: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    screener_slug: Mapped[Optional[str]] = mapped_column(String(64))

    announcements: Mapped[list["Announcement"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )

    @property
    def yahoo_ticker(self) -> str:
        suffix = ".BO" if self.exchange.upper() == "BSE" else ".NS"
        return f"{self.symbol}{suffix}"


class PriceBar(Base):
    """End-of-day OHLCV. Split/bonus adjusted at source."""

    __tablename__ = "price_bars"
    __table_args__ = (
        UniqueConstraint("company_id", "trade_date", name="uq_price_company_date"),
        Index("ix_price_company_date", "company_id", "trade_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    trade_date: Mapped[date] = mapped_column(Date)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)
    # Derived on ingest so the alert evaluator stays a pure read.
    pct_change: Mapped[Optional[float]] = mapped_column(Float)
    volume_ratio: Mapped[Optional[float]] = mapped_column(Float)


class Announcement(Base, TimestampMixin):
    __tablename__ = "announcements"
    __table_args__ = (
        UniqueConstraint("dedup_hash", name="uq_announcement_dedup"),
        Index("ix_ann_filed_score", "filed_at", "score"),
        Index("ix_ann_company_filed", "company_id", "filed_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    dedup_hash: Mapped[str] = mapped_column(String(32), index=True)

    filed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    subject: Mapped[str] = mapped_column(Text)
    body: Mapped[Optional[str]] = mapped_column(Text)
    attachment_url: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16), default="NSE")

    category: Mapped[str] = mapped_column(String(32), index=True, default="unclassified")
    classified_by: Mapped[str] = mapped_column(String(16), default="rules")  # rules|llm
    materiality: Mapped[float] = mapped_column(Float, default=0.3)
    score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    is_routine: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    summary: Mapped[Optional[str]] = mapped_column(Text)
    # Rich rendering payload: results numbers or an incoming-executive bio.
    # JSON rather than extra columns because the shape differs per category
    # and the frontend renders a different component for each.
    enrichment: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    company: Mapped[Company] = relationship(back_populates="announcements")


class AlertRule(Base, TimestampMixin):
    """User-configurable thresholds. One row per profile; the prototype ships
    a single 'default' profile but the shape supports many."""

    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile: Mapped[str] = mapped_column(String(32), unique=True, default="default")
    volume_multiple: Mapped[float] = mapped_column(Float, default=2.0)
    price_move_pct: Mapped[float] = mapped_column(Float, default=4.0)
    watched_categories: Mapped[str] = mapped_column(
        Text, default="results,M&A,management_change,fund_raise,litigation"
    )
    min_score: Mapped[float] = mapped_column(Float, default=0.45)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    @property
    def category_list(self) -> list[str]:
        return [c.strip() for c in (self.watched_categories or "").split(",") if c.strip()]


class AlertEvent(Base):
    """A fired alert. Persisted so the same trigger is not re-announced on
    every ingest run — the investor should see it once."""

    __tablename__ = "alert_events"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_alert_fingerprint"),
        Index("ix_alert_created", "triggered_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    fingerprint: Mapped[str] = mapped_column(String(48), index=True)
    kind: Mapped[str] = mapped_column(String(24))  # price|volume|category
    headline: Mapped[str] = mapped_column(Text)
    detail: Mapped[Optional[str]] = mapped_column(Text)
    severity: Mapped[float] = mapped_column(Float, default=0.5)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    announcement_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("announcements.id", ondelete="SET NULL")
    )
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)


class QuarterlyResult(Base, TimestampMixin):
    """Headline numbers extracted from a results filing, in crore."""

    __tablename__ = "quarterly_results"
    __table_args__ = (
        UniqueConstraint("company_id", "fiscal_year", "quarter", name="uq_result_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    fiscal_year: Mapped[int] = mapped_column(Integer)
    quarter: Mapped[int] = mapped_column(Integer)

    revenue: Mapped[Optional[float]] = mapped_column(Float)
    ebitda: Mapped[Optional[float]] = mapped_column(Float)
    pbt: Mapped[Optional[float]] = mapped_column(Float)
    pat: Mapped[Optional[float]] = mapped_column(Float)
    ebitda_derived: Mapped[bool] = mapped_column(Boolean, default=False)

    source_url: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    @property
    def label(self) -> str:
        return f"Q{self.quarter} FY{str(self.fiscal_year)[-2:]}"


class Document(Base, TimestampMixin):
    """A primary-source document: annual report or concall transcript."""

    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("url_hash", name="uq_document_url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(24))  # annual_report|transcript
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    url_hash: Mapped[str] = mapped_column(String(32), index=True)
    fiscal_year: Mapped[Optional[int]] = mapped_column(Integer)
    quarter: Mapped[Optional[int]] = mapped_column(Integer)
    extracted: Mapped[bool] = mapped_column(Boolean, default=False)
    char_count: Mapped[int] = mapped_column(Integer, default=0)


class GuidanceClaim(Base, TimestampMixin):
    """A checkable forward-looking statement made by management on a call.

    Vague optimism is filtered out upstream; if a row exists here it has a
    metric and either a number or an unambiguous direction.
    """

    __tablename__ = "guidance_claims"
    __table_args__ = (Index("ix_claim_company_period", "company_id", "said_fy", "said_q"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    document_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )

    said_fy: Mapped[int] = mapped_column(Integer)
    said_q: Mapped[int] = mapped_column(Integer)
    metric: Mapped[str] = mapped_column(String(64))         # revenue growth, EBITDA margin...
    direction: Mapped[Optional[str]] = mapped_column(String(16))  # expand|contract|flat|grow
    target_low: Mapped[Optional[float]] = mapped_column(Float)
    target_high: Mapped[Optional[float]] = mapped_column(Float)
    unit: Mapped[Optional[str]] = mapped_column(String(16))  # pct|crore|x
    horizon_fy: Mapped[Optional[int]] = mapped_column(Integer)
    horizon_q: Mapped[Optional[int]] = mapped_column(Integer)
    speaker: Mapped[Optional[str]] = mapped_column(String(96))
    quote: Mapped[str] = mapped_column(Text)

    outcomes: Mapped[list["GuidanceOutcome"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )


class GuidanceOutcome(Base, TimestampMixin):
    """The verdict on a claim once the relevant period has reported."""

    __tablename__ = "guidance_outcomes"
    __table_args__ = (
        UniqueConstraint("claim_id", "assessed_fy", "assessed_q", name="uq_outcome_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("guidance_claims.id", ondelete="CASCADE"))
    assessed_fy: Mapped[int] = mapped_column(Integer)
    assessed_q: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))  # met|missed|partial|too_early|unverifiable
    actual_value: Mapped[Optional[float]] = mapped_column(Float)
    reasoning: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)

    claim: Mapped[GuidanceClaim] = relationship(back_populates="outcomes")


class LLMUsage(Base):
    """Per-call token accounting. Powers the cost figure in the UI and the
    efficiency claim in the writeup."""

    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    stage: Mapped[str] = mapped_column(String(48), index=True)
    tier: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(16))
    model: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached: Mapped[bool] = mapped_column(Boolean, default=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)


class IngestRun(Base):
    """Audit trail for the nightly job; surfaced on the admin screen."""

    __tablename__ = "ingest_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="running")
    prices_ingested: Mapped[int] = mapped_column(Integer, default=0)
    announcements_ingested: Mapped[int] = mapped_column(Integer, default=0)
    alerts_fired: Mapped[int] = mapped_column(Integer, default=0)
    fell_back_to_seed: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
