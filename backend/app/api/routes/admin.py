"""Operational endpoints: trigger ingest, inspect cost, check health."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Announcement, Company, IngestRun, LLMUsage
from app.db.session import get_session
from app.schemas.common import HealthOut, UsageOut
from app.services.ingest.runner import run_ingest

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/health", response_model=HealthOut)
def health(session: Session = Depends(get_session)) -> HealthOut:
    last_run = session.scalars(
        select(IngestRun).order_by(IngestRun.started_at.desc()).limit(1)
    ).first()
    return HealthOut(
        status="ok",
        environment=settings.environment,
        data_mode=settings.data_mode,
        llm_provider=settings.llm_provider,
        companies=session.scalar(select(func.count(Company.id))) or 0,
        announcements=session.scalar(select(func.count(Announcement.id))) or 0,
        last_ingest=last_run.finished_at if last_run else None,
    )


@router.post("/ingest", response_model=dict)
async def trigger_ingest(
    background: BackgroundTasks, discover_fundamentals: bool = False
) -> dict:
    """Run the pipeline now.

    Returns immediately and runs in the background: a full pass can take
    minutes, and a demo should never sit on a hung request.
    """
    background.add_task(run_ingest, discover_fundamentals=discover_fundamentals)
    return {"started": True, "detail": "Ingest running in the background."}


@router.post("/ingest/sync", response_model=dict)
async def trigger_ingest_sync(discover_fundamentals: bool = False) -> dict:
    """Blocking variant, for scripts and first-boot seeding."""
    summary = await run_ingest(discover_fundamentals=discover_fundamentals)
    return {
        "prices": summary.prices,
        "announcements": summary.announcements,
        "classified_by_rules": summary.classified_by_rules,
        "classified_by_model": summary.classified_by_model,
        "enriched": summary.enriched,
        "alerts": summary.alerts,
        "used_seed": summary.used_seed,
        "errors": summary.errors,
    }


@router.get("/usage", response_model=UsageOut)
def usage(session: Session = Depends(get_session)) -> UsageOut:
    """Token accounting — the number that backs the efficiency claim."""
    rows = list(session.scalars(select(LLMUsage)))
    if not rows:
        return UsageOut()
    cached = sum(1 for r in rows if r.cached)
    by_stage: dict[str, int] = {}
    for row in rows:
        by_stage[row.stage] = by_stage.get(row.stage, 0) + row.input_tokens + row.output_tokens
    return UsageOut(
        calls=len(rows),
        cached_calls=cached,
        input_tokens=sum(r.input_tokens for r in rows),
        output_tokens=sum(r.output_tokens for r in rows),
        by_stage=dict(sorted(by_stage.items(), key=lambda kv: kv[1], reverse=True)),
        cache_hit_rate=round(cached / len(rows), 3),
    )


@router.get("/runs", response_model=list[dict])
def runs(session: Session = Depends(get_session), limit: int = 10) -> list[dict]:
    rows = session.scalars(
        select(IngestRun).order_by(IngestRun.started_at.desc()).limit(limit)
    )
    return [
        {
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "status": r.status,
            "prices": r.prices_ingested,
            "announcements": r.announcements_ingested,
            "alerts": r.alerts_fired,
            "used_seed": r.fell_back_to_seed,
            "notes": r.notes,
        }
        for r in rows
    ]
