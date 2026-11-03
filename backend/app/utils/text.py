"""Text normalisation, hashing and chunking."""
from __future__ import annotations

import hashlib
import re
import unicodedata

_WS_RE = re.compile(r"[ \t\u00a0]+")
_BLANK_RE = re.compile(r"\n{3,}")


def normalise(text: str) -> str:
    """Collapse whitespace and unicode variants so hashing is stable."""
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WS_RE.sub(" ", text)
    return _BLANK_RE.sub("\n\n", text).strip()


def content_hash(*parts: object) -> str:
    """Deterministic key for caching and deduplication."""
    digest = hashlib.sha256()
    for part in parts:
        digest.update(normalise(str(part)).encode("utf-8"))
        digest.update(b"\x1f")
    return digest.hexdigest()[:32]


def truncate(text: str, limit: int, suffix: str = "…") -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - len(suffix))].rstrip() + suffix


def chunk_text(text: str, size: int = 12_000, overlap: int = 800) -> list[str]:
    """Split on paragraph boundaries, never mid-sentence.

    Overlap exists because a guidance statement frequently straddles a
    question and its answer; losing that boundary loses the claim.
    """
    text = normalise(text)
    if not text:
        return []
    if len(text) <= size:
        return [text]
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    buffer = ""
    for para in paragraphs:
        if len(buffer) + len(para) + 2 <= size:
            buffer = f"{buffer}\n\n{para}" if buffer else para
            continue
        if buffer:
            chunks.append(buffer)
            buffer = (buffer[-overlap:] + "\n\n" + para) if overlap else para
        else:  # single paragraph longer than the window
            for i in range(0, len(para), size - overlap):
                chunks.append(para[i : i + size])
            buffer = ""
    if buffer:
        chunks.append(buffer)
    return chunks


def keyword_prefilter(chunks: list[str], keywords: list[str]) -> list[str]:
    """Drop chunks that cannot contain what we are looking for.

    Guidance language is formulaic. Filtering before the model call is the
    single biggest cost saving in the pull pipeline — typically 60-75% of a
    transcript never reaches an LLM.
    """
    if not keywords:
        return chunks
    pattern = re.compile("|".join(re.escape(k) for k in keywords), re.I)
    kept = [c for c in chunks if pattern.search(c)]
    return kept or chunks[:2]  # never return nothing


def first_sentence(text: str, limit: int = 180) -> str:
    text = normalise(text)
    match = re.search(r"(?<=[.!?])\s", text)
    sentence = text[: match.start()] if match else text
    return truncate(sentence, limit)
