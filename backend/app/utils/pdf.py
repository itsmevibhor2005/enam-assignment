"""PDF text extraction with an on-disk cache.

Annual reports run to 300 pages. Extraction is slow and perfectly
deterministic, so it is cached by content hash and never repeated.
"""
from __future__ import annotations

import io
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.utils.text import content_hash, normalise

log = get_logger(__name__)


def _cache_path(key: str) -> Path:
    directory = settings.cache_dir / "pdf"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{key}.txt"


def extract_text(data: bytes, *, source: str = "", max_pages: int = 400) -> str:
    """Extract text from a PDF, returning '' rather than raising.

    A scanned, image-only filing yields no text. That is a legitimate outcome
    — the caller treats an empty string as 'no primary data here' and moves
    on instead of crashing the ingest run.
    """
    key = content_hash(source or "", len(data), data[:2048])
    cached = _cache_path(key)
    if cached.exists():
        return cached.read_text(encoding="utf-8")

    text = ""
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = []
            for index, page in enumerate(pdf.pages):
                if index >= max_pages:
                    break
                pages.append(page.extract_text() or "")
            text = normalise("\n\n".join(pages))
    except Exception as exc:  # noqa: BLE001 - any malformed PDF lands here
        log.warning("pdf extraction failed for %s: %s", source or "<bytes>", exc)
        text = ""

    if text:
        cached.write_text(text, encoding="utf-8")
    return text


def looks_like_scan(text: str, page_estimate: int = 1) -> bool:
    """Heuristic: almost no characters per page means an image-only filing."""
    return len(text) < 200 * max(1, page_estimate)
