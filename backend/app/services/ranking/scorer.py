"""Prioritisation.

The product thesis is filtering, so this module is the product. It answers
one question: of the 60 filings that landed overnight, which four should the
investor see before breakfast?

    score = category_weight
          x materiality
          x recency_decay
          x (1 + market_corroboration)
          x size_factor

Each term earns its place:

* category_weight / materiality — what kind of thing this is, and how big an
  instance of that kind it is.
* recency_decay — a filing from 20 hours ago matters less than one from 20
  minutes ago, but not *much* less inside one digest window, so the decay is
  gentle and floors out rather than reaching zero.
* market_corroboration — the interesting term. A press release that coincided
  with a 6% move and triple volume is a different object from the same press
  release on a flat day. Price action is the market's own vote on
  materiality, and it is the one signal that is not self-reported by the
  company.
* size_factor — a mid-cap filing moves a mid-cap position more than the same
  filing moves a large-cap one.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.services.classification.taxonomy import ROUTINE_THRESHOLD, weight_for
from app.utils.numbers import clamp

# Half-life in hours. At 36h a filing retains ~0.5 of its recency term, so
# a week-long digest still ranks on substance rather than purely on clock.
_RECENCY_HALF_LIFE_H = 36.0
_RECENCY_FLOOR = 0.35

_SIZE_FACTOR = {"large": 0.92, "mid": 1.0, "small": 1.06}

# Corroboration caps out: a 20% move should not make an ESOP allotment
# important, it should make the *price* the headline.
_MAX_CORROBORATION = 0.60


@dataclass(frozen=True, slots=True)
class MarketContext:
    """Same-day market behaviour for the filing's company."""

    pct_change: float | None = None
    volume_ratio: float | None = None

    @property
    def corroboration(self) -> float:
        """0 to _MAX_CORROBORATION, from how unusual the day was."""
        move = 0.0
        if self.pct_change is not None:
            # 3% move contributes ~0.2; 8% contributes ~0.4; saturating.
            move = 0.4 * math.tanh(abs(self.pct_change) / 6.0) * 2
        volume = 0.0
        if self.volume_ratio is not None and self.volume_ratio > 1.2:
            volume = 0.25 * math.tanh((self.volume_ratio - 1.2) / 1.5)
        return clamp(move * 0.6 + volume, 0.0, _MAX_CORROBORATION)


@dataclass(frozen=True, slots=True)
class ScoredItem:
    score: float
    is_routine: bool
    components: dict[str, float]


def recency_decay(hours_old: float) -> float:
    if hours_old <= 0:
        return 1.0
    decayed = 0.5 ** (hours_old / _RECENCY_HALF_LIFE_H)
    return clamp(decayed, _RECENCY_FLOOR, 1.0)


def score_announcement(
    *,
    category: str,
    materiality: float,
    hours_old: float,
    market: MarketContext | None = None,
    market_cap_band: str | None = None,
    in_portfolio: bool = True,
) -> ScoredItem:
    """Score one filing. Pure function — trivially testable, no I/O."""
    weight = weight_for(category)
    materiality = clamp(float(materiality or 0.0), 0.0, 1.0)
    decay = recency_decay(hours_old)
    corroboration = market.corroboration if market else 0.0
    size = _SIZE_FACTOR.get((market_cap_band or "mid").lower(), 1.0)

    # Research on a non-portfolio name is informational; it should never
    # outrank something the investor actually owns.
    ownership = 1.0 if in_portfolio else 0.55

    raw = weight * materiality * decay * (1.0 + corroboration) * size * ownership
    score = round(clamp(raw, 0.0, 1.0), 4)

    # Routine is judged on the un-decayed substance of the item, not on how
    # old it is. Otherwise a genuinely material filing silently demotes
    # itself into the collapsed row after two days, which is exactly the
    # failure the product exists to prevent.
    substance = weight * materiality * (1.0 + corroboration)
    return ScoredItem(
        score=score,
        is_routine=substance < ROUTINE_THRESHOLD,
        components={
            "category_weight": round(weight, 3),
            "materiality": round(materiality, 3),
            "recency": round(decay, 3),
            "corroboration": round(corroboration, 3),
            "size": size,
            "ownership": ownership,
        },
    )


def headline_count(scores: list[float], *, threshold: float = 0.45, cap: int = 6) -> int:
    """How many items to present as 'things that matter' above the fold.

    Deliberately not a fixed number. A quiet day should say 'nothing much
    happened' rather than manufacturing five headlines to fill a screen.
    """
    return min(cap, sum(1 for s in scores if s >= threshold))
