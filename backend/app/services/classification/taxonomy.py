"""Announcement taxonomy and the weights that drive prioritisation.

Categories follow the brief's reference document. The weights are ours: they
encode a view about what actually moves a position, and they are the most
opinionated numbers in the codebase.

Base materiality answers "if I know nothing else about this filing, how much
should it interrupt me?" Results and M&A interrupt. An ESOP allotment does
not, ever.
"""
from __future__ import annotations

from enum import StrEnum


class Category(StrEnum):
    RESULTS = "results"
    MA = "M&A"
    FUND_RAISE = "fund_raise"
    MANAGEMENT_CHANGE = "management_change"
    LITIGATION = "litigation"
    INSIDER_TRADING = "insider_trading"
    EARNINGS_CALL = "earnings_call"
    INVESTOR_MEETINGS = "investor_meetings"
    CREDIT_RATING = "credit_rating"
    DIVIDEND = "dividend"
    BONUS_SPLIT = "bonus_split"
    CAPEX = "capex"
    PRESS_RELEASE = "press_release"
    POSTAL_BALLOT = "postal_ballot"
    AGM_EGM = "agm_egm"
    PLEDGING = "pledging"
    UNCLASSIFIED = "unclassified"


CATEGORY_WEIGHT: dict[str, float] = {
    Category.RESULTS: 1.00,
    Category.MA: 0.95,
    Category.LITIGATION: 0.80,
    Category.FUND_RAISE: 0.78,
    Category.MANAGEMENT_CHANGE: 0.75,
    Category.CREDIT_RATING: 0.68,
    Category.CAPEX: 0.62,
    Category.PLEDGING: 0.60,
    Category.BONUS_SPLIT: 0.50,
    Category.DIVIDEND: 0.48,
    Category.INSIDER_TRADING: 0.45,
    Category.PRESS_RELEASE: 0.46,
    Category.EARNINGS_CALL: 0.38,
    Category.INVESTOR_MEETINGS: 0.20,
    Category.POSTAL_BALLOT: 0.15,
    Category.AGM_EGM: 0.12,
    Category.UNCLASSIFIED: 0.05,
}

# Below this score an item is folded into the collapsed "routine" row. It is
# never hidden outright — the investor can always open it.
ROUTINE_THRESHOLD = 0.30

# Categories where a one-line LLM summary genuinely adds something. For a
# dividend declaration the subject line already says everything.
SUMMARY_WORTHY = {
    Category.RESULTS,
    Category.MA,
    Category.LITIGATION,
    Category.FUND_RAISE,
    Category.MANAGEMENT_CHANGE,
    Category.CREDIT_RATING,
    Category.CAPEX,
    Category.PRESS_RELEASE,
    Category.PLEDGING,
}

CATEGORY_LABEL: dict[str, str] = {
    Category.RESULTS: "Results",
    Category.MA: "M&A",
    Category.FUND_RAISE: "Fund raise",
    Category.MANAGEMENT_CHANGE: "Management",
    Category.LITIGATION: "Litigation",
    Category.INSIDER_TRADING: "Insider trade",
    Category.EARNINGS_CALL: "Earnings call",
    Category.INVESTOR_MEETINGS: "Investor meeting",
    Category.CREDIT_RATING: "Credit rating",
    Category.DIVIDEND: "Dividend",
    Category.BONUS_SPLIT: "Bonus / split",
    Category.CAPEX: "Capex",
    Category.PRESS_RELEASE: "Press release",
    Category.POSTAL_BALLOT: "Postal ballot",
    Category.AGM_EGM: "AGM / EGM",
    Category.PLEDGING: "Pledging",
    Category.UNCLASSIFIED: "Routine",
}


def weight_for(category: str) -> float:
    return CATEGORY_WEIGHT.get(category, CATEGORY_WEIGHT[Category.UNCLASSIFIED])


def label_for(category: str) -> str:
    return CATEGORY_LABEL.get(category, "Routine")


def is_valid(category: str) -> bool:
    return category in CATEGORY_WEIGHT
