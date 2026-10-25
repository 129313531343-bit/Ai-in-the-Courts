"""Automatic verification of a proposed tracker row against its judgment text.

Each check returns (check name, passed?, detail). A row with any failed
check is flagged for Luc's review.

What these checks can establish: every value rests on a quote that appears in
the judgment text, at the paragraph stated; MNC, title and impugned citations
are copied exactly; and the row agrees with deterministic facts (the MNC read
by regex, court-code family-law status, the court's own paragraph count).

What they cannot establish: whether the model *read* a quote correctly (e.g.
classified a costs order or a characterisation correctly). The keyword checks
below are only a tripwire for that, so a passing row is "auto_verified", not
human-verified. Accuracy of the readings is estimated from Luc's random
spot-check.
"""

import re

from aic.doctext import Doc
from aic.textnorm import norm_passage

# Words a supporting quote should contain for each characterisation (tripwire, not proof).
CHARACTERISATION_CUES = {
    "non_existent": ["not exist", "non-existent", "nonexistent", "fictitious", "fictional", "fabricat", "no such",
                     "invented", "hallucinat", "fake", "does not appear to exist", "imaginary", "no record",
                     "could not be found", "unable to find", "could not find", "no case", "no decision"],
    "not_located": ["locate", "could not be found", "cannot be found", "unable to find", "could not find",
                    "not able to find", "no record", "no such", "could find", "hallucinat", "unable to identify",
                    "no trace"],
    "false_quote": ["quot", "passage", "does not appear", "not contain", "words", "no paragraph"],
    "wrong_pinpoint": ["paragraph", "pinpoint", "page", "para"],
    "exists_but_misdescribed": ["stand for", "not authority", "misdescri", "misrepresent", "misquot", "not support",
                                "does not deal", "did not", "does not", "is not about", "not about", "irrelevant",
                                "no relevance", "not relevant", "different", "inaccura", "incorrect", "erroneous",
                                "wrong", "not match", "refers to", "is the citation for", "nothing in", "not say",
                                "no paragraph", "unrelated", "concerned", "rather"],
    "not_stated": [],
}
HEADER_FIELDS = {"mnc", "title_as_published", "court", "date", "party_type", "family_law_matter"}
CHARLOTIN_PARTY = {"Lawyer": "lawyer", "Pro Se Litigant": "self_represented", "Expert": "expert",
                   "Judge": "judicial_officer"}
_NUM_WORDS = re.compile(r"preceding\s+[a-z\- ]+\s*\((\d{1,4})\)\s+numbered\s+paragraphs", re.IGNORECASE)


def same_mnc(a: str, b: str) -> bool:
    """Equal as citations: '[2025] QIRC 046', '[2025] QIRC 46' and (as printed by some
    decisions, e.g. ATMO) '2025 ATMO 264' vs '[2025] ATMO 264' are the same decision."""
    pat = re.compile(r"^\[?\s*((?:19|20)\d\d)\s*\]?\s+([A-Z][A-Za-z0-9]{1,11})\s+(\d{1,5})$")
    ma, mb = pat.match((a or "").strip()), pat.match((b or "").strip())
    return bool(ma and mb) and (ma.group(1), ma.group(2), int(ma.group(3))) == \
        (mb.group(1), mb.group(2), int(mb.group(3)))


def in_text(needle: str, doc: Doc) -> bool:
    """Exact containment after normalisation (case-sensitive)."""
    n = norm_passage(needle)
    return bool(n) and n in doc.flat


def title_in_text(title: str, doc: Doc, window: int = 400) -> bool:
    """The title appears in the judgment: exactly, ignoring case, or with its words in order
    within a short span (cover pages lay parties out on separate lines with role labels
    such as 'Applicant' between them). No word may be absent, so nothing can be added."""
    if in_text(title, doc) or norm_passage(title).lower() in doc.flat.lower():
        return True
    words = re.findall(r"\w+", norm_passage(title).lower())
    flat = doc.flat.lower()
    if not words:
        return False
    for m in re.finditer(re.escape(words[0]), flat):
        pos, ok = m.end(), True
        for w in words[1:]:
            nxt = flat.find(w, pos)
            if nxt < 0 or nxt - m.start() > window:
                ok = False
                break
            pos = nxt + len(w)
        if ok:
            return True
    return False


def certified_paragraphs(doc: Doc) -> int | None:
    """The court's own count, e.g. 'I certify that the preceding eighty-four (84) numbered paragraphs ...'."""
    m = _NUM_WORDS.search(doc.flat)
    return int(m.group(1)) if m else None


def check_row(fields: dict, quotes: dict[str, dict], doc: Doc, meta: dict, charlotin: dict,
              dropped: list[str]) -> list[tuple[str, bool, str]]:
    """fields: Pass B output after enforce_quotes; quotes: quote_id -> quote_checks row (as dict)."""
    out: list[tuple[str, bool, str]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        out.append((name, ok, detail))

    used = sorted({q for v in fields.values() for q in (
        [i for c in v for i in c["quote_ids"]] if isinstance(v, list) else v.get("quote_ids", []))})
    bad = [q for q in used if not quotes.get(q, {}).get("pass")]
    add("quotes_found_in_judgment", not bad, ",".join(bad))
    # family_law_matter is decided from the court code, so a dropped unsupported value there is harmless.
    real_drops = [d for d in dropped if d != "family_law_matter"]
    add("no_unsupported_values_dropped", not real_drops, ";".join(real_drops))
    # Header facts (MNC, title, date, court, parties) sit above paragraph 1, so only the
    # analytical fields must point to a numbered paragraph.
    analytical = sorted({q for k, v in fields.items() if k not in HEADER_FIELDS for q in (
        [i for c in v for i in c["quote_ids"]] if isinstance(v, list) else v.get("quote_ids", []))})
    # Orders and catchwords above paragraph 1 ('front_matter') are a proper source for a consequence.
    no_para = [q for q in analytical if quotes.get(q, {}).get("pass") and not quotes[q].get("paragraph")
               and quotes[q].get("location") != "front_matter"]
    add("quotes_have_paragraph_numbers", not no_para, ",".join(no_para))

    cert = certified_paragraphs(doc)
    detected = max(doc.markers.values()) if doc.markers else None
    add("paragraph_count_matches_court_certificate", cert is None or cert == detected,
        f"certificate says {cert}, detected up to {detected}" if cert is not None else "no certificate")

    mnc = fields["mnc"]["value"]
    add("mnc_matches_document_header", bool(mnc) and same_mnc(mnc, meta.get("mnc_from_document", "")),
        f"pass_b={mnc!r} regex={meta.get('mnc_from_document')!r}")
    title = fields["title_as_published"]["value"]
    add("title_found_in_judgment", bool(title) and title_in_text(title, doc), title)

    for c in fields["impugned_citations"]:
        cit = c["citation_verbatim"]
        add("impugned_citation_copied_exactly", in_text(cit, doc), cit)
        cues = CHARACTERISATION_CUES.get(c["characterisation"], [])
        support = " ".join(quotes.get(q, {}).get("cited_text", "") for q in c["quote_ids"]).lower()
        add("characterisation_has_textual_cue", not cues or any(k in support for k in cues),
            f"{cit}: {c['characterisation']}")
        add("impugned_by_the_court_itself", c.get("asserted_by") == "court",
            f"{cit}: asserted_by={c.get('asserted_by')!r}")

    errs = set(fields["error_types"]["values"])
    if fields["impugned_citations"] and not errs:
        add("error_types_consistent", False, "impugned citations listed but no error type")
    # No rule ties "non_existent_case" to the listed citations: courts often reproduce only some
    # impugned citations (e.g. the misdescribed ones) and decline to reproduce the fabricated ones.

    fam = fields["family_law_matter"]["value"]
    fam_code = meta.get("family_law_proposed") == "True"
    add("family_law_agrees_with_court_code", (fam == "yes") == fam_code or fam == "unclear" and not fam_code,
        f"pass_b={fam!r} court_code_family={fam_code}")
    if meta.get("copy_source_markers", "").find("Wikisource") >= 0:
        add("official_copy", False, "secondary copy (Wikisource): check against the official version")

    party = fields["party_type"]["value"]
    ch_party = CHARLOTIN_PARTY.get(charlotin.get("Party(ies)", ""), "")
    # A blank party type is an absence of support, not a disagreement (the tracker then shows Charlotin's coding).
    add("party_type_agrees_with_charlotin", not ch_party or not party or party == ch_party,
        f"pass_b={party!r} charlotin={charlotin.get('Party(ies)', '')!r}")
    ch_out = (charlotin.get("Outcome", "") + " " + charlotin.get("Professional Sanction", "")).lower()
    if ch_out.strip():
        ch_ref = "referr" in ch_out
        ours = fields["regulator_referred"]["value"] == "yes"
        add("referral_agrees_with_charlotin", ours == ch_ref, f"pass_b={ours} charlotin={ch_ref}")
    return out


def cohen_kappa(a: list[str], b: list[str]) -> float | None:
    """Cohen's kappa for two raters' labels on the same items (None if undefined)."""
    if not a or len(a) != len(b):
        return None
    n = len(a)
    labels = set(a) | set(b)
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    pe = sum((a.count(k) / n) * (b.count(k) / n) for k in labels)
    return None if pe == 1 else (po - pe) / (1 - pe)
