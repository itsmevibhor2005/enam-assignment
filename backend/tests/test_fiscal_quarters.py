"""The fiscal-quarter maths underpins every QoQ/YoY comparison in the app."""
from datetime import datetime

from app.utils.dates import IST, FiscalQuarter, last_n_quarters


def test_june_is_q1_of_next_fiscal_year():
    assert FiscalQuarter.from_date(datetime(2026, 6, 15, tzinfo=IST)) == FiscalQuarter(2027, 1)


def test_january_is_q4_of_current_fiscal_year():
    assert FiscalQuarter.from_date(datetime(2027, 1, 20, tzinfo=IST)) == FiscalQuarter(2027, 4)


def test_q1_previous_quarter_crosses_the_fiscal_year_boundary():
    # The QoQ comparator for Q1 FY27 is Q4 FY26, not Q4 FY27.
    assert FiscalQuarter(2027, 1).previous() == FiscalQuarter(2026, 4)


def test_year_ago_keeps_the_quarter_number():
    assert FiscalQuarter(2027, 2).year_ago() == FiscalQuarter(2026, 2)


def test_label_format():
    assert FiscalQuarter(2027, 3).label == "Q3 FY27"


def test_parse_handles_common_renderings():
    for text in ["Q2 FY27", "q2fy2027", "guidance for Q2, FY 27"]:
        assert FiscalQuarter.parse(text) == FiscalQuarter(2027, 2)


def test_parse_returns_none_on_garbage():
    assert FiscalQuarter.parse("next year sometime") is None


def test_future_quarter_has_not_elapsed():
    future = FiscalQuarter(2031, 1)
    assert future.has_elapsed() is False


def test_last_n_quarters_excludes_the_unreported_current_quarter():
    quarters = last_n_quarters(4, now=datetime(2026, 11, 1, tzinfo=IST))
    # November 2026 sits in Q3 FY27, which has not reported.
    assert quarters[0] == FiscalQuarter(2027, 2)
    assert len(quarters) == 4
    assert quarters[-1] == FiscalQuarter(2026, 3)
