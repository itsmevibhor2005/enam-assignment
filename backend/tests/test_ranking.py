"""Scoring is the product; these tests pin its intended behaviour."""
from app.services.ranking.scorer import (
    MarketContext,
    headline_count,
    recency_decay,
    score_announcement,
)
from app.services.classification.taxonomy import Category


def _score(**kwargs):
    base = dict(category=Category.RESULTS, materiality=0.9, hours_old=2.0)
    base.update(kwargs)
    return score_announcement(**base)


def test_results_outrank_routine_paperwork():
    results = _score()
    routine = _score(category=Category.UNCLASSIFIED, materiality=0.05)
    assert results.score > routine.score
    assert routine.is_routine and not results.is_routine


def test_recency_decays_but_never_to_zero():
    assert recency_decay(0) == 1.0
    assert recency_decay(36) < recency_decay(2)
    assert recency_decay(10_000) >= 0.35


def test_a_material_item_does_not_become_routine_just_by_ageing():
    fresh = _score(hours_old=1)
    stale = _score(hours_old=400)
    assert stale.score < fresh.score
    assert stale.is_routine is False  # substance is judged without decay


def test_market_corroboration_lifts_an_ambiguous_filing():
    quiet = _score(category=Category.PRESS_RELEASE, materiality=0.45)
    moving = _score(
        category=Category.PRESS_RELEASE,
        materiality=0.45,
        market=MarketContext(pct_change=6.4, volume_ratio=3.2),
    )
    assert moving.score > quiet.score


def test_corroboration_cannot_rescue_genuine_noise():
    noise = _score(
        category=Category.UNCLASSIFIED,
        materiality=0.05,
        market=MarketContext(pct_change=20.0, volume_ratio=9.0),
    )
    assert noise.is_routine is True


def test_non_portfolio_names_rank_below_holdings():
    owned = _score()
    watched = _score(in_portfolio=False)
    assert owned.score > watched.score


def test_scores_stay_in_range():
    extreme = _score(
        materiality=1.0,
        market=MarketContext(pct_change=40.0, volume_ratio=20.0),
        market_cap_band="small",
    )
    assert 0.0 <= extreme.score <= 1.0


def test_headline_count_is_honest_on_a_quiet_day():
    assert headline_count([0.1, 0.2, 0.05]) == 0
    assert headline_count([0.9, 0.7, 0.5, 0.2]) == 3
    assert headline_count([0.9] * 20) == 6  # capped
