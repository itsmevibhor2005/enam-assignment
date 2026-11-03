"""Aggregate router."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import admin, alerts, digest, research

api_router = APIRouter(prefix="/api")
api_router.include_router(digest.router)
api_router.include_router(research.router)
api_router.include_router(alerts.router)
api_router.include_router(admin.router)
