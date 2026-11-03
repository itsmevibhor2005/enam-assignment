"""Pull-side contracts."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

GuidanceStatus = Literal["met", "missed", "partial", "too_early", "unverifiable"]


class GuidanceItem(BaseModel):
    claim_id: int
    said_in: str
    metric: str
    promise: str
    horizon: str | None = None
    speaker: str | None = None
    quote: str
    status: GuidanceStatus = "too_early"
    actual_value: float | None = None
    reasoning: str | None = None
    confidence: float = 0.5


class GuidanceScorecard(BaseModel):
    met: int = 0
    missed: int = 0
    partial: int = 0
    too_early: int = 0
    unverifiable: int = 0

    @property
    def judged(self) -> int:
        return self.met + self.missed + self.partial


class Segment(BaseModel):
    name: str
    share_pct: float | None = None
    note: str | None = None


class SnapshotOut(BaseModel):
    what_it_does: str | None = None
    segments: list[Segment] = Field(default_factory=list)
    revenue_mix_note: str | None = None
    trajectory: str | None = None
    balance_sheet: dict[str, Any] = Field(default_factory=dict)
    cash_quality: str | None = None
    watch_items: list[str] = Field(default_factory=list)


class SourceRef(BaseModel):
    title: str
    url: str
    kind: str


class ResearchOut(BaseModel):
    symbol: str
    name: str
    in_portfolio: bool = False
    snapshot: SnapshotOut | None = None
    bull: list[str] = Field(default_factory=list)
    bear: list[str] = Field(default_factory=list)
    guidance: list[GuidanceItem] = Field(default_factory=list)
    scorecard: GuidanceScorecard = Field(default_factory=GuidanceScorecard)
    quarters_covered: list[str] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    guidance_note: str | None = None
