"""Push-side contracts."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ResultsRow(BaseModel):
    metric: str
    value: float | None = None
    qoq_pct: float | None = None
    yoy_pct: float | None = None
    prev_quarter: float | None = None
    year_ago: float | None = None
    sign_flip: bool = False


class ResultsEnrichment(BaseModel):
    type: Literal["results"] = "results"
    period: str
    basis: str = "consolidated"
    unit: str = "Rs crore"
    ebitda_derived: bool = False
    confidence: float = 0.5
    rows: list[ResultsRow] = Field(default_factory=list)
    ebitda_margin_pct: float | None = None
    pat_margin_pct: float | None = None


class PersonEnrichment(BaseModel):
    type: Literal["person"] = "person"
    name: str
    role: str | None = None
    direction: str = "unclear"
    effective: str | None = None
    background: str | None = None
    tenure_note: str | None = None


class AnnouncementOut(ORMModel):
    id: int
    symbol: str
    company_name: str
    filed_at: datetime
    subject: str
    summary: str | None = None
    category: str
    category_label: str
    score: float
    is_routine: bool
    attachment_url: str | None = None
    source: str = "NSE"
    pct_change: float | None = None
    volume_ratio: float | None = None
    enrichment: dict[str, Any] | None = None


class DigestOut(BaseModel):
    """The home screen payload.

    ``headline`` is the plain sentence at the top of the app. It is computed
    server-side so the phrasing stays consistent and the client stays dumb.
    """

    window_hours: int
    from_ts: datetime
    to_ts: datetime
    headline: str
    material: list[AnnouncementOut] = Field(default_factory=list)
    routine: list[AnnouncementOut] = Field(default_factory=list)
    routine_count: int = 0
    companies_affected: int = 0


class AlertOut(ORMModel):
    id: int
    symbol: str
    company_name: str
    kind: str
    headline: str
    detail: str | None = None
    severity: float
    triggered_at: datetime
    acknowledged: bool = False
    announcement_id: int | None = None


class AlertRuleIn(BaseModel):
    """Threshold configuration. Bounds are enforced here because a 0%
    price threshold would alert on every company every day."""

    volume_multiple: float = Field(default=2.0, ge=1.1, le=20.0)
    price_move_pct: float = Field(default=4.0, ge=0.5, le=30.0)
    watched_categories: list[str] = Field(default_factory=list)
    min_score: float = Field(default=0.45, ge=0.0, le=1.0)
    enabled: bool = True


class AlertRuleOut(AlertRuleIn):
    profile: str = "default"
