"""Exchanges republish the same event; the digest must not."""
from datetime import datetime, timedelta

from app.services.ingest.announcements import make_dedup_hash
from app.utils.dates import IST


def test_same_filing_at_a_corrected_timestamp_collides():
    base = datetime(2026, 10, 30, 9, 15, tzinfo=IST)
    subject = "Audited Financial Results for the quarter ended September 30, 2026"
    assert make_dedup_hash("POLYCAB", subject, base) == make_dedup_hash(
        "POLYCAB", subject, base + timedelta(hours=4)
    )


def test_boilerplate_variants_collide():
    base = datetime(2026, 10, 30, 9, 15, tzinfo=IST)
    a = "Intimation of acquisition of 60% stake under Regulation 30"
    b = "Acquisition of 60% stake"
    assert make_dedup_hash("DIXON", a, base) == make_dedup_hash("DIXON", b, base)


def test_different_companies_do_not_collide():
    base = datetime(2026, 10, 30, 9, 15, tzinfo=IST)
    subject = "Audited Financial Results"
    assert make_dedup_hash("INFY", subject, base) != make_dedup_hash("TCS", subject, base)


def test_different_days_do_not_collide():
    subject = "Audited Financial Results"
    d1 = datetime(2026, 10, 30, 9, 15, tzinfo=IST)
    assert make_dedup_hash("INFY", subject, d1) != make_dedup_hash(
        "INFY", subject, d1 + timedelta(days=1)
    )
