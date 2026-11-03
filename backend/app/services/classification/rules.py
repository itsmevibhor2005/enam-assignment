"""Deterministic first-pass classifier.

Exchange subject lines are highly formulaic, so regex handles the clear
majority for free. Order matters: patterns are evaluated most-specific first
because "Board Meeting Intimation for Financial Results" is results, not a
generic board meeting, and "Resignation of Statutory Auditor" is routine
paperwork rather than a management change.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.classification.taxonomy import Category


@dataclass(frozen=True, slots=True)
class RuleMatch:
    category: str
    materiality: float
    rule: str


# (compiled pattern, category, materiality, rule name)
_RULES: list[tuple[re.Pattern[str], str, float, str]] = [
    # --- explicit non-material paperwork, checked first -------------------
    # Either word order: NSE files both "ESOP allotment" and "Allotment of
    # equity shares under Employee Stock Option Scheme".
    (re.compile(
        r"(?:\b(?:esop|employee stock option)\b.{0,60}?\b(?:allot|grant|exercis)"
        r"|\b(?:allot|grant|exercis)\w*\b.{0,60}?\b(?:esop|employee stock option))",
        re.I),
     Category.UNCLASSIFIED, 0.05, "esop_allotment"),
    (re.compile(r"\b(reg(ulation)?\.?\s*(74|40|7\(3\)|13)|certificate under|compliance certificate)", re.I),
     Category.UNCLASSIFIED, 0.04, "compliance_certificate"),
    (re.compile(r"\b(newspaper (publication|advertisement)|published in newspaper)", re.I),
     Category.UNCLASSIFIED, 0.05, "newspaper"),
    (re.compile(r"\b(appointment|re-?appointment|resignation).{0,30}\b(statutory|internal|secretarial|cost) auditor", re.I),
     Category.UNCLASSIFIED, 0.12, "auditor_change"),
    (re.compile(r"\b(business responsibility|brsr|sustainability report|esg report)", re.I),
     Category.UNCLASSIFIED, 0.08, "esg_report"),
    (re.compile(r"\b(trading window|closure of trading window)", re.I),
     Category.UNCLASSIFIED, 0.05, "trading_window"),
    (re.compile(r"\b(loss of share certificate|duplicate share|unclaimed (shares|dividend)|iepf)", re.I),
     Category.UNCLASSIFIED, 0.03, "share_admin"),

    # --- results ----------------------------------------------------------
    (re.compile(r"\b(financial results|audited results|unaudited results|results for the (quarter|year)|standalone and consolidated results)", re.I),
     Category.RESULTS, 0.90, "results_filing"),
    (re.compile(r"\bboard meeting\b.{0,60}\b(financial results|results)", re.I),
     Category.RESULTS, 0.70, "board_meeting_results"),
    (re.compile(r"\b(investor presentation|earnings presentation|results presentation|shareholders? letter)", re.I),
     Category.RESULTS, 0.60, "results_deck"),

    # --- M&A --------------------------------------------------------------
    (re.compile(r"\b(acquisition|acquire[sd]?|merger|amalgamation|demerger|scheme of arrangement|joint venture|slump sale|divestment|stake sale|strategic investment)", re.I),
     Category.MA, 0.92, "m_and_a"),
    (re.compile(r"\b(incorporation|formation) of (a )?(wholly owned )?subsidiary", re.I),
     Category.MA, 0.55, "subsidiary_formation"),

    # --- fund raise -------------------------------------------------------
    (re.compile(r"\b(rights issue|qip|qualified institution|preferential (allotment|issue)|buy-?back|fund rais|debenture|commercial paper|ncd\b|issue of equity shares)", re.I),
     Category.FUND_RAISE, 0.80, "fund_raise"),

    # --- management -------------------------------------------------------
    (re.compile(r"\b(appointment|resignation|cessation|retirement|re-?designation|demise).{0,60}\b(managing director|ceo|chief executive|cfo|chief financial|chairman|whole[- ]time director|independent director|company secretary|key managerial)", re.I),
     Category.MANAGEMENT_CHANGE, 0.82, "kmp_change"),
    (re.compile(r"\b(change in (management|directorate|key managerial personnel))", re.I),
     Category.MANAGEMENT_CHANGE, 0.78, "management_change"),

    # --- insider trading, before litigation ------------------------------
    # These cite SEBI regulations in their subject line and would otherwise
    # be swept up as regulatory action against the company.
    (re.compile(
        r"\b(sast\b|insider trading|prohibition of insider trading|pit regulation"
        r"|regulation 7\s*\(\s*2\s*\)|regulation 29\s*\(|promoter (buying|selling))",
        re.I),
     Category.INSIDER_TRADING, 0.42, "insider_trading"),

    # --- litigation / regulatory -----------------------------------------
    (re.compile(r"\b(sebi|nclt|nclat|income tax|gst|show cause|penalty|fine|adjudication order|search and seizure|insolvency|cirp|litigation|writ petition|arbitration award)", re.I),
     Category.LITIGATION, 0.80, "litigation"),

    # --- corporate actions -------------------------------------------------
    (re.compile(r"\b(interim dividend|final dividend|dividend)\b", re.I),
     Category.DIVIDEND, 0.45, "dividend"),
    (re.compile(r"\b(bonus issue|stock split|sub-?division of (equity )?shares|face value split)", re.I),
     Category.BONUS_SPLIT, 0.55, "bonus_split"),
    (re.compile(r"\b(credit rating|rating (action|revision)|crisil|icra\b|care ratings|india ratings)", re.I),
     Category.CREDIT_RATING, 0.62, "credit_rating"),
    (re.compile(r"\b(pledge|invocation of pledge|release of pledge|encumbrance)", re.I),
     Category.PLEDGING, 0.65, "pledging"),

    # --- capex / operations ------------------------------------------------
    (re.compile(r"\b(capacity expansion|new plant|greenfield|brownfield|capital expenditure|commissioning of|commence(ment)? of commercial production)", re.I),
     Category.CAPEX, 0.68, "capex"),
    (re.compile(r"\b(order win|receipt of order|letter of award|loa\b|bags? (an )?order|contract award)", re.I),
     Category.PRESS_RELEASE, 0.74, "order_win"),
    (re.compile(r"\b(clarification|rumou?r verification|response to (news|query))", re.I),
     Category.PRESS_RELEASE, 0.50, "clarification"),

    # --- calls and meetings -------------------------------------------------
    (re.compile(r"\b(earnings call|conference call|concall|audio recording|transcript)", re.I),
     Category.EARNINGS_CALL, 0.35, "earnings_call"),
    (re.compile(r"\b(analyst|institutional investor).{0,30}meet|investor meet|schedule of meeting", re.I),
     Category.INVESTOR_MEETINGS, 0.18, "investor_meeting"),
    (re.compile(r"\b(postal ballot)", re.I), Category.POSTAL_BALLOT, 0.15, "postal_ballot"),
    (re.compile(r"\b(annual general meeting|extra-?ordinary general meeting|\bagm\b|\begm\b)", re.I),
     Category.AGM_EGM, 0.12, "agm_egm"),

    # --- generic fallbacks, last -------------------------------------------
    (re.compile(r"\b(press release|media release|product launch|partnership|mou\b|tie-?up)", re.I),
     Category.PRESS_RELEASE, 0.45, "press_release"),
    (re.compile(r"\bboard meeting\b", re.I), Category.UNCLASSIFIED, 0.25, "board_meeting_generic"),
]


def classify(subject: str, body: str | None = None) -> RuleMatch | None:
    """Return the first matching rule, or None to escalate to the model."""
    haystack = f"{subject or ''}\n{(body or '')[:600]}"
    if not haystack.strip():
        return None
    for pattern, category, materiality, name in _RULES:
        if pattern.search(haystack):
            return RuleMatch(category=str(category), materiality=materiality, rule=name)
    return None
