"""Two-stage classification pipeline.

Stage 1 is regex and costs nothing. Stage 2 batches whatever is left into a
single cheap-tier call — 20 subject lines per request, not 20 requests. On a
typical night the rules handle most of the feed and the model sees a handful.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import Announcement, Company
from app.llm.client import get_llm
from app.llm.prompts import classify as prompts
from app.services.classification import rules
from app.services.classification.taxonomy import Category, is_valid
from app.utils.numbers import clamp

log = get_logger(__name__)

_BATCH_SIZE = 20


@dataclass(slots=True)
class ClassificationStats:
    by_rules: int = 0
    by_model: int = 0
    unresolved: int = 0


async def classify_batch(
    session: Session, announcements: list[Announcement], companies: dict[int, Company]
) -> ClassificationStats:
    stats = ClassificationStats()
    pending: list[Announcement] = []

    for announcement in announcements:
        match = rules.classify(announcement.subject, announcement.body)
        if match:
            announcement.category = match.category
            announcement.materiality = match.materiality
            announcement.classified_by = "rules"
            stats.by_rules += 1
        else:
            pending.append(announcement)

    for start in range(0, len(pending), _BATCH_SIZE):
        chunk = pending[start : start + _BATCH_SIZE]
        resolved = await _classify_with_model(chunk, companies)
        stats.by_model += resolved
        stats.unresolved += len(chunk) - resolved

    session.flush()
    log.info(
        "classified %d by rules, %d by model, %d fell back",
        stats.by_rules, stats.by_model, stats.unresolved,
    )
    return stats


async def _classify_with_model(
    chunk: list[Announcement], companies: dict[int, Company]
) -> int:
    rows = [
        {
            "id": index,
            "company": companies[a.company_id].symbol if a.company_id in companies else "",
            "subject": a.subject,
        }
        for index, a in enumerate(chunk)
    ]
    payload = await get_llm().complete_json(
        stage="announcement_classification",
        system=prompts.CLASSIFY_SYSTEM,
        prompt=prompts.build_classify_prompt(rows),
        tier="cheap",
        max_tokens=1200,
    )

    items = []
    if isinstance(payload, dict):
        items = payload.get("items") or []
    elif isinstance(payload, list):
        items = payload

    resolved = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("id"))
            announcement = chunk[index]
        except (TypeError, ValueError, IndexError):
            continue
        category = str(item.get("category") or "").strip()
        if not is_valid(category):
            continue
        try:
            materiality = clamp(float(item.get("materiality", 0.3)), 0.0, 1.0)
        except (TypeError, ValueError):
            materiality = 0.3
        announcement.category = category
        announcement.materiality = materiality
        announcement.classified_by = "llm"
        resolved += 1

    # Anything the model skipped keeps a conservative default rather than
    # being dropped: an unclassified filing is still visible, just low.
    for announcement in chunk:
        if announcement.classified_by != "llm":
            announcement.category = str(Category.UNCLASSIFIED)
            announcement.materiality = 0.15
            announcement.classified_by = "rules"
    return resolved
