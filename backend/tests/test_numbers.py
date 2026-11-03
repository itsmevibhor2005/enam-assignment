"""Parsing filings, and refusing to produce misleading percentages."""
from app.utils.numbers import margin_pct, parse_amount, pct_change


def test_parses_plain_crore():
    assert parse_amount("5,842", "crore") == 5842.0


def test_converts_lakh_to_crore():
    assert parse_amount("12,500", "lakh") == 125.0


def test_parenthesised_values_are_negative():
    assert parse_amount("(412.5)", "crore") == -412.5


def test_inline_unit_wins_over_declared_unit():
    assert parse_amount("250 million") == 25.0


def test_nil_and_dashes_are_none_not_zero():
    for raw in ["-", "—", "NA", "Nil", ""]:
        assert parse_amount(raw) is None


def test_pct_change_refuses_sign_flip():
    # A swing from a Rs 50 cr loss to a Rs 100 cr profit has no sensible %.
    assert pct_change(100.0, -50.0) is None


def test_pct_change_refuses_near_zero_base():
    assert pct_change(100.0, 0.0) is None


def test_pct_change_normal_case():
    assert pct_change(110.0, 100.0) == 10.0


def test_margin_pct():
    assert margin_pct(798.0, 5842.0) == 13.66
