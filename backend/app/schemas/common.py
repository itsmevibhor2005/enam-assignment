"""Shared response contracts."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CompanyOut(ORMModel):
    symbol: str
    name: str
    sector: str | None = None
    market_cap_band: str | None = None
    in_portfolio: bool = True


class PriceOut(ORMModel):
    trade_date: str
    close: float
    volume: float
    pct_change: float | None = None
    volume_ratio: float | None = None


class ErrorOut(BaseModel):
    detail: str
    code: str = "error"


class HealthOut(BaseModel):
    status: str
    environment: str
    data_mode: str
    llm_provider: str
    companies: int
    announcements: int
    last_ingest: datetime | None = None


class UsageOut(BaseModel):
    """Token accounting, surfaced in the UI as a cost line."""

    calls: int = 0
    cached_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    by_stage: dict[str, int] = Field(default_factory=dict)
    cache_hit_rate: float = 0.0
