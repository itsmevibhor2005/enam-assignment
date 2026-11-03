"""Application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import FinnError
from app.core.logging import configure_logging, get_logger
from app.db.session import init_db

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_db()
    scheduler = None
    if settings.scheduler_enabled:
        scheduler = _start_scheduler()
    log.info(
        "%s up — mode=%s provider=%s", settings.app_name,
        settings.data_mode, settings.llm_provider,
    )
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


def _start_scheduler():
    """Nightly ingest after market close.

    Wrapped in a try: a scheduler failure must not stop the API from serving
    the data that is already in the database.
    """
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger

        from app.services.ingest.runner import run_ingest
        from app.utils.dates import IST

        scheduler = AsyncIOScheduler(timezone=IST)
        scheduler.add_job(
            run_ingest,
            CronTrigger(hour=settings.ingest_hour_ist, minute=0),
            id="nightly_ingest",
            max_instances=1,
            coalesce=True,       # a missed run catches up once, not N times
            misfire_grace_time=3600,
        )
        scheduler.start()
        log.info("scheduler started — nightly ingest at %02d:00 IST", settings.ingest_hour_ist)
        return scheduler
    except Exception as exc:  # noqa: BLE001
        log.warning("scheduler unavailable: %s", exc)
        return None


app = FastAPI(
    title="FINN API",
    description="Financial investment agent — push digest and pull research.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(FinnError)
async def handle_finn_error(_: Request, exc: FinnError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.__class__.__name__},
    )


@app.exception_handler(Exception)
async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong on our side.", "code": "internal"},
    )


app.include_router(api_router)


@app.get("/", tags=["admin"])
def root() -> dict:
    return {"service": settings.app_name, "docs": "/docs"}
