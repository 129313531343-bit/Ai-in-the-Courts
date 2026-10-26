"""Impugned citations Luc checked himself, in rows whose AI-extracted details are held back.

Luc read these 47 citations against the judgments in the review page (Fake citations tab,
saved to data/review/impugned_checks.json, local; DECISIONS.md D031 E2). Because a person
read them, they can be published although the rest of those rows waits for AustLII (D024's
carve-out; D035). His prose corrections are fixed values here, each with his note (D034).
Used by scripts/12_build_tracker.py (publication) and scripts/28_build_fabricated.py
(evaluation items).
"""

import json
from functools import cache

from aic import ROOT

CHECKS = ROOT / "data/review/impugned_checks.json"

# (tracker id, citation number from 1): fixed values from Luc's notes of 26 Oct 2026.
CORRECTIONS = {
    ("AIC-0033", 1): {"label": "not_located",
                      "note": "Luc: the court describes a false case name but qualifies its finding about "
                              "genuineness ([36]-[37]); recorded as not located, not as an unqualified finding."},
    ("AIC-0033", 2): {"label": "not_located",
                      "note": "Luc marked this for fixing without text; his note on citation 1 covers the same "
                              "discussion ([35]-[37]), so the same label is used."},
    ("AIC-0036", 1): {"citation": "[Redacted (Second Case)]", "note": "Luc: footnote marker removed."},
    ("AIC-0036", 2): {"citation": "[Redacted (Third Case)]", "note": "Luc: footnote marker removed."},
    ("AIC-0104", 1): {"label": "wrong_pinpoint",
                      "note": "Luc: the court's criticism concerns paragraph [7] specifically."},
}
# Citations the court lists that the extraction missed (Luc's notes). The court's own
# characterisation was not given, so they are not_stated until Luc says otherwise.
ADDED = [
    ("AIC-0036", "Section 85(3) of the Industrial Relations Act 1996 (NSW)", "not_stated",
     "Luc: missing from the extraction."),
    ("AIC-0038", "FWC Rule XXXX", "not_stated",
     "Luc: paragraph [15] describes an incomplete citation (a placeholder), not a finding that it does not exist."),
    ("AIC-0098", "Domestic Building Contract Act 1995 (Vic)", "not_stated", "Luc: missing from the extraction."),
    ("AIC-0098", "Civil Procedure Act 2010 (Vic)", "not_stated", "Luc: missing from the extraction."),
]


@cache
def _tracker_ids() -> dict[str, str]:
    import csv
    with (ROOT / "data/reference/id_map.csv").open(newline="") as f:
        return {r["charlotin_row"]: r["id"] for r in csv.DictReader(f)}


@cache
def _checks() -> dict:
    return json.loads(CHECKS.read_text()) if CHECKS.exists() else {}


def checked(row: str) -> list[dict] | None:
    """Luc's final list for a Charlotin row, or None if he has not checked it.

    Each item: {"citation", "label", "note"}. Raises if a correction has no fixed value yet,
    so an untranslated note can never be published as it stands.
    """
    decided = _checks().get(row)
    if not decided:
        return None
    tid = _tracker_ids()[row]
    extracted = json.loads((ROOT / f"data/interim/pass_b/{row}.json").read_text())["fields"]["impugned_citations"]
    out = []
    for i, (cite, verdict) in enumerate(zip(extracted, decided["citations"], strict=True), 1):
        fix = CORRECTIONS.get((tid, i), {})
        if verdict["verdict"] != "correct" and not fix:
            raise ValueError(f"{tid} citation {i}: Luc's note is not yet a fixed value: {verdict['value']!r}")
        out.append({"citation": " ".join(fix.get("citation", cite["citation_verbatim"]).split()),
                    "label": fix.get("label", cite["characterisation"]),
                    "note": fix.get("note", "Checked by Luc (D031 E2).")})
    out += [{"citation": c, "label": label, "note": note} for t, c, label, note in ADDED if t == tid]
    return out
