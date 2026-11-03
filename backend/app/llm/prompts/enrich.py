"""Prompts for push-side rich rendering: results numbers and executive bios."""
from __future__ import annotations

RESULTS_SYSTEM = """You extract headline numbers from an Indian quarterly results filing.

Return ONLY this JSON:
{
  "period": {"fy": <int, e.g. 2027>, "q": <1-4>},
  "unit": "crore" | "lakh" | "million",
  "current":   {"revenue": n, "ebitda": n, "pbt": n, "pat": n},
  "prev_quarter": {"revenue": n, "ebitda": n, "pbt": n, "pat": n},
  "year_ago":  {"revenue": n, "ebitda": n, "pbt": n, "pat": n},
  "ebitda_derived": <bool>,
  "basis": "consolidated" | "standalone",
  "confidence": <0.0-1.0>
}

Critical rules:
- Use null for any figure not present. NEVER estimate, interpolate or carry a
  number across from a different column. A null is correct; a guess is not.
- Indian filings run an April-March fiscal year. The quarter ending June is
  Q1 of the fiscal year ending the following March: June 2026 is Q1 FY2027.
- Results filings print three columns: current quarter, preceding quarter,
  corresponding quarter of the previous year. Map them to current,
  prev_quarter and year_ago respectively. If only some columns exist, fill
  what you can and null the rest.
- Prefer consolidated figures when both are present; say which you used.
- EBITDA is usually not stated. If you derive it (revenue minus total
  expenses, adding back depreciation and finance cost), set ebitda_derived
  true. If you cannot derive it cleanly, use null.
- Figures in brackets are negative.
- Set confidence below 0.5 if the table structure was ambiguous."""


def build_results_prompt(company: str, text: str) -> str:
    return f"Company: {company}\n\nResults filing text:\n{text[:45000]}"


PERSON_SYSTEM = """You summarise an incoming or outgoing executive for a portfolio
manager who has never heard of them.

Return ONLY:
{"name": "<str>", "role": "<str>", "direction": "joining"|"leaving"|"unclear",
 "effective": "<str or null>", "background": "<str or null>",
 "tenure_note": "<str or null>"}

- background: at most 25 words on where they came from, from the filing text
  only. If the filing gives no background, use null. Do not supply it from
  memory.
- tenure_note: only if the filing states how long the departing person served.
- Never speculate about why someone is leaving."""


def build_person_prompt(subject: str, body: str | None) -> str:
    return f"Subject: {subject}\n\nFiling text:\n{(body or '')[:8000]}"
