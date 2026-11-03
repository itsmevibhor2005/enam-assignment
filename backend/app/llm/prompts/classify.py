"""Prompts for the bulk classification tier."""
from __future__ import annotations

from app.services.classification.taxonomy import CATEGORY_WEIGHT

_CATEGORIES = ", ".join(sorted(CATEGORY_WEIGHT))

CLASSIFY_SYSTEM = f"""You classify Indian stock-exchange filings for a fund's alert system.

Return ONLY a JSON object of the form {{"items": [...]}}. Each item:
{{"id": <int>, "category": "<one of: {_CATEGORIES}>", "materiality": <0.0-1.0>}}

materiality is how much this filing should interrupt a portfolio manager's day:
  0.0-0.2  routine compliance paperwork nobody reads
  0.3-0.5  worth knowing, not worth stopping for
  0.6-0.8  changes how you think about the position
  0.9-1.0  you act on this today

Judge the specific filing, not the category average. A tiny related-party
order win is not a 0.8 just because order wins can be. Scale matters: a
number given relative to company size raises materiality; an unquantified
announcement lowers it. If the subject is too vague to judge, use
"unclassified" with materiality 0.15. Never invent a category outside the
list."""


def build_classify_prompt(rows: list[dict]) -> str:
    lines = [
        f'{{"id": {r["id"]}, "company": "{r["company"]}", "subject": "{r["subject"][:300]}"}}'
        for r in rows
    ]
    return "Classify each filing:\n" + "\n".join(lines)


SUMMARY_SYSTEM = """You write one-line summaries of Indian exchange filings for a
portfolio manager who will read 30 of them in two minutes.

Return ONLY {"summary": "<text>"}.

Rules:
- One sentence, at most 20 words, no trailing period needed.
- Lead with the number or the name. "Acquires 51% of X for Rs 420 cr" beats
  "The company announced that it has acquired a stake".
- Never repeat the company name; the interface already shows it.
- Never use "announced", "intimated", "informed the exchange", or "is pleased to".
- If the filing contains no substance beyond its own title, return the empty
  string rather than padding it."""


def build_summary_prompt(subject: str, body: str | None) -> str:
    extract = (body or "")[:3000]
    return f"Subject: {subject}\n\nFiling text:\n{extract or '(no body text available)'}"
