"""The rules classifier carries most of the feed, so its edges matter."""
from app.services.classification import rules
from app.services.classification.taxonomy import Category


def test_results_filing():
    match = rules.classify("Audited Financial Results for the quarter ended September 30, 2026")
    assert match and match.category == Category.RESULTS
    assert match.materiality > 0.8


def test_board_meeting_for_results_is_results_not_generic():
    match = rules.classify("Intimation of Board Meeting to consider financial results")
    assert match and match.category == Category.RESULTS


def test_esop_allotment_is_routine_despite_containing_allotment():
    match = rules.classify("Allotment of equity shares under Employee Stock Option Scheme")
    assert match and match.category == Category.UNCLASSIFIED
    assert match.materiality < 0.1


def test_auditor_resignation_is_not_a_management_change():
    # Ordered before the KMP rule for exactly this reason.
    match = rules.classify("Resignation of Statutory Auditor")
    assert match and match.category == Category.UNCLASSIFIED


def test_cfo_resignation_is_a_management_change():
    match = rules.classify("Resignation of Chief Financial Officer and appointment of successor")
    assert match and match.category == Category.MANAGEMENT_CHANGE


def test_acquisition_is_m_and_a():
    match = rules.classify("Intimation of acquisition of 60% equity stake in a manufacturer")
    assert match and match.category == Category.MA


def test_compliance_certificate_is_routine():
    match = rules.classify("Certificate under Regulation 74(5) of SEBI Regulations")
    assert match and match.category == Category.UNCLASSIFIED


def test_sebi_warning_is_litigation():
    match = rules.classify("Disclosure of SEBI administrative warning")
    assert match and match.category == Category.LITIGATION


def test_unknown_subject_escalates_to_the_model():
    assert rules.classify("Miscellaneous corporate update regarding internal matters") is None
