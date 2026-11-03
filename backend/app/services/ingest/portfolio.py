"""The demo portfolio.

Chosen for spread, not conviction: five sectors, three size bands, and a mix
of heavy filers and quiet ones so the digest has something to filter. The
engine never reads this list — it is seed data for the demo only, and every
pull-side path takes an arbitrary NSE symbol.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Holding:
    symbol: str
    name: str
    sector: str
    band: str
    screener_slug: str | None = None


PORTFOLIO: list[Holding] = [
    Holding("RELIANCE", "Reliance Industries", "Energy & Retail", "large"),
    Holding("HDFCBANK", "HDFC Bank", "Banking", "large"),
    Holding("INFY", "Infosys", "IT Services", "large"),
    Holding("TATAMOTORS", "Tata Motors", "Automobiles", "large"),
    Holding("SUNPHARMA", "Sun Pharmaceutical", "Pharma", "large"),
    Holding("LT", "Larsen & Toubro", "Capital Goods", "large"),
    Holding("ITC", "ITC", "FMCG", "large"),
    Holding("POLYCAB", "Polycab India", "Electricals", "mid"),
    Holding("DIXON", "Dixon Technologies", "Electronics Mfg", "mid"),
    Holding("PERSISTENT", "Persistent Systems", "IT Services", "mid"),
    Holding("CUMMINSIND", "Cummins India", "Capital Goods", "mid"),
    Holding("APLAPOLLO", "APL Apollo Tubes", "Metals", "mid"),
    Holding("CDSL", "Central Depository Services", "Capital Markets", "mid"),
    Holding("KPITTECH", "KPIT Technologies", "Auto Tech", "mid"),
    Holding("JUBLFOOD", "Jubilant FoodWorks", "QSR", "mid"),
    Holding("CAMS", "Computer Age Management", "Capital Markets", "mid"),
    Holding("RATNAMANI", "Ratnamani Metals", "Metals", "small"),
    Holding("GRANULES", "Granules India", "Pharma", "small"),
    Holding("ROUTE", "Route Mobile", "Telecom Software", "small"),
    Holding("SHAILY", "Shaily Engineering", "Plastics", "small"),
]

# Outside the portfolio, used to demonstrate that pull generalises.
RESEARCH_DEMO: list[Holding] = [
    Holding("TITAN", "Titan Company", "Consumer Discretionary", "large"),
    Holding("ASTRAL", "Astral", "Building Materials", "mid"),
    Holding("VGUARD", "V-Guard Industries", "Electricals", "small"),
    Holding("AFFLE", "Affle India", "AdTech", "mid"),
]


def all_holdings() -> list[tuple[Holding, bool]]:
    return [(h, True) for h in PORTFOLIO] + [(h, False) for h in RESEARCH_DEMO]
