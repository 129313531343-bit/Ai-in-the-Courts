"""Luc's answers to the automatic checks that flagged 37 tracker rows (DECISIONS.md D041, D042).

He answered in the review page's Flagged rows tab (data/review/flag_checks.json, local).
Answers chosen from a menu (a fake citation's label, the party type, a referral, who
asserted a citation) apply as they are. Answers he typed as notes are fixed values in FIXES
below, each kept with his note, so a note is never published as it stands. Used by
scripts/12_build_tracker.py.
"""

import json
from functools import cache

import pandas as pd

from aic import ROOT

CHECKS = ROOT / "data/review/flag_checks.json"

# (tracker id, check) -> tracker values Luc's typed answer sets.
FIXES: dict[tuple[str, str], dict] = {
    ("AIC-0004", "quotes_have_paragraph_numbers"): {
        "pinpoints": "orders, [1], [5], [6], [17], [18]",
        "note": "Luc: the quoted reasons are in numbered paragraphs [1], [5], [6], [17] and [18]; the referral "
                "direction is an order."},
    ("AIC-0004", "paragraph_count_matches_court_certificate"): {
        "pinpoints": "orders, [1], [5], [6], [17], [18]",
        "note": "Luc: the judgment has numbered paragraphs; paragraph references restored (as above)."},
    ("AIC-0019", "mnc_matches_document_header"): {
        "mnc": "[2025] QIRC 141",
        "note": "Luc: [2025] QIRC 141, not 121; the quoted findings belong to Ivins v KMA Consulting Engineers "
                "Pty Ltd & Ors."},
    ("AIC-0021", "quotes_have_paragraph_numbers"): {
        "pinpoints": "[19], [20], [21]",
        "note": "Luc: the discussion is at [19]-[21]; aic.docxnum, reading the Word file's own numbering, places "
                "the quotes in the same paragraphs."},
    ("AIC-0021", "mnc_matches_document_header"): {"mnc": "[2025] VCC 868", "note": "Luc: [2025] VCC 868."},
    ("AIC-0021", "title_found_in_judgment"): {"title_as_published": "Page v Long", "note": "Luc: Page v Long."},
    ("AIC-0023", "quotes_have_paragraph_numbers"): {
        "pinpoints": "orders, [4], [8], [10], [14], [15]",
        "note": "Luc: the reasons are in numbered paragraphs; the costs direction and the leave to amend are "
                "orders. Paragraph numbers from aic.docxnum (the Word file's own numbering)."},
    ("AIC-0023", "title_found_in_judgment"): {
        "title_as_published": "Murray on behalf of the Wamba Wemba Native Title Claim Group v State of Victoria",
        "note": "Luc: title as published."},
    ("AIC-0077", "title_found_in_judgment"): {
        "title_as_published": "Duc Nam Nguyen v Turk Hava Yollari Anonim Ortakligi (Turkish Airlines)",
        "note": "Luc: title as published."},
    ("AIC-0107", "quotes_have_paragraph_numbers"): {
        "pinpoints": "[1], [2]",
        "note": "Luc: the dismissal is at [1]; the passages on AI use, inadequate checking and misapplied "
                "authorities are at [2]."},
}
# Answers that confirm or qualify without changing a value.
NOTES = {
    ("AIC-0009", "official_copy"): "Luc: reproductions agree on the citation, court and date (31 January 2025); "
                                   "the official version could not be accessed, so that check is unconfirmed.",
    ("AIC-0047", "party_type_agrees_with_charlotin"): "Luc (unsure): the judgment attributes the submissions to the "
                                                      "appellant or the union; it does not say which supplied the "
                                                      "false citations. Party type published blank.",
}
# Which tracker column each check is about.
FIELD_OF = {
    "characterisation_has_textual_cue": "impugned_citations", "impugned_by_the_court_itself": "impugned_citations",
    "impugned_citation_copied_exactly": "impugned_citations", "party_type_agrees_with_charlotin": "party_type",
    "referral_agrees_with_charlotin": "regulator_referred", "title_found_in_judgment": "title_as_published",
    "mnc_matches_document_header": "mnc", "quotes_have_paragraph_numbers": "pinpoints",
    "paragraph_count_matches_court_certificate": "pinpoints", "official_copy": None,
}


@cache
def _answers() -> dict:
    return json.loads(CHECKS.read_text()) if CHECKS.exists() else {}


@cache
def _failed() -> pd.DataFrame:
    vc = pd.read_csv(ROOT / "data/interim/verification_checks.csv", dtype=str, keep_default_na=False)
    return vc[vc.passed == "False"]


def _norm(s: str) -> str:
    return " ".join(s.split())


def apply(row: str, tid: str, fields: dict) -> tuple[dict, dict, set[str]] | None:
    """Apply Luc's answers for a Charlotin row: (fields, tracker overrides, columns he answered), or None.

    The item keys match the review page's (scripts/13_review_server.py flags()): "<check>:<n>", n
    counting the row's failed checks in order. Raises if a typed change has no fixed value.
    """
    decided = _answers().get(row)
    if not decided:
        return None
    overrides: dict = {"verified_on": decided.get("reviewed_on", "")}
    answered: set[str] = set()
    covered: set[str] = set()  # impugned citations Luc answered about
    failed = _failed()[_failed().charlotin_row == row]
    for n, (_, f) in enumerate(failed.iterrows()):
        a = decided["items"].get(f"{f.check}:{n}")
        if a is None:
            raise ValueError(f"{tid}: no answer for {f.check}:{n}")
        if FIELD_OF.get(f.check):
            answered.add(FIELD_OF[f.check])
        verdict, value = a["verdict"], a.get("value")
        if f.check in ("characterisation_has_textual_cue", "impugned_by_the_court_itself"):
            citation = f.detail.rsplit(": ", 1)[0]
            covered.add(_norm(citation))
            key = "characterisation" if f.check == "characterisation_has_textual_cue" else "asserted_by"
            for c in fields.get("impugned_citations", []):
                if _norm(c["citation_verbatim"]) == _norm(citation):
                    if verdict == "corrected":
                        c[key] = value
                    elif verdict == "unsure" and key == "characterisation":
                        c[key] = "not_stated"
        elif f.check in ("party_type_agrees_with_charlotin", "referral_agrees_with_charlotin"):
            name = "party_type" if f.check.startswith("party") else "regulator_referred"
            if verdict == "corrected":
                fields[name]["value"] = value
            elif verdict == "unsure":
                fields[name]["value"] = ""
        elif f.check == "impugned_citation_copied_exactly":
            covered.add(_norm(f.detail))
            if verdict != "correct":
                raise ValueError(f"{tid}: correction to a citation's wording not yet a fixed value: {value!r}")
        elif verdict == "corrected":
            fix = FIXES.get((tid, f.check))
            if fix is None:
                raise ValueError(f"{tid} {f.check}: Luc's note is not yet a fixed value: {value!r}")
            overrides.update({k: v for k, v in fix.items() if k != "note"})
        elif verdict == "unsure" and FIELD_OF.get(f.check) and (tid, f.check) not in NOTES:
            overrides[FIELD_OF[f.check]] = ""
    # A list Luc only partly read is not his reading of the list: publish it only if he covered all of it.
    listed = {_norm(c["citation_verbatim"]) for c in fields.get("impugned_citations", [])}
    if "impugned_citations" in answered and not listed <= covered:
        answered.discard("impugned_citations")
    return fields, overrides, answered
