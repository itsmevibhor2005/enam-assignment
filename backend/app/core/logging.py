"""Structured-ish logging setup. One configure() call, used by main and jobs."""
from __future__ import annotations

import logging
import sys

from app.core.config import settings

_FORMAT = "%(asctime)s %(levelname)-7s %(name)-28s %(message)s"


def configure_logging() -> None:
    root = logging.getLogger()
    if root.handlers:  # already configured (e.g. uvicorn reload)
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt="%H:%M:%S"))
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())
    for noisy in ("httpx", "urllib3", "apscheduler.executors.default"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
