"""Content-addressed completion cache.

Keyed on (stage, model, system, prompt). A re-run of the nightly job after a
crash costs nothing, and a grader hitting the same ticker twice gets an
instant second response.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.utils.text import content_hash


def _path(key: str) -> Path:
    directory = settings.cache_dir / "llm"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{key}.json"


def make_key(stage: str, model: str, system: str, prompt: str) -> str:
    return content_hash(stage, model, system, prompt)


def get(key: str) -> str | None:
    if not settings.llm_cache_enabled:
        return None
    path = _path(key)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))["text"]
    except (ValueError, KeyError, OSError):
        return None


def put(key: str, text: str) -> None:
    if not settings.llm_cache_enabled:
        return
    try:
        _path(key).write_text(json.dumps({"text": text}), encoding="utf-8")
    except OSError:
        pass
