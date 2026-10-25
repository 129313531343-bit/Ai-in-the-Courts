from aic.doctext import Doc, Line
from aic.verify import certified_paragraphs, check_row, cohen_kappa


def doc():
    return Doc([
        Line(1, "Brown v Green [2025] FCA 12", 72, 12),
        Line(1, "1 The applicant filed submissions citing Smith v Jones [2020] HCA 99.", 72, 12),
        Line(1, "2 No such case exists. It is fictitious.", 72, 12),
        Line(2, "3 I refer the matter to the Legal Services Commissioner.", 72, 12),
        Line(2, "I certify that the preceding three (3) numbered paragraphs are a true copy.", 72, 12),
    ], 2)


def f(value="", ids=()):
    return {"value": value, "quote_ids": list(ids)}


def fields(**over):
    base = {
        "mnc": f("[2025] FCA 12", ["Q1"]), "title_as_published": f("Brown v Green", ["Q1"]),
        "court": f(), "date": f(), "party_type": f("lawyer", ["Q2"]), "ai_use": f(),
        "ai_tool_if_stated": f(), "error_types": {"values": ["non_existent_case"], "quote_ids": ["Q2"]},
        "impugned_citations": [{"citation_verbatim": "Smith v Jones [2020] HCA 99",
                                "characterisation": "non_existent", "asserted_by": "court", "quote_ids": ["Q2"]}],
        "consequence": {"values": ["regulator_referral"], "quote_ids": ["Q3"]},
        "regulator_referred": f("yes", ["Q3"]), "practice_note_cited": f(), "family_law_matter": f("no", ["Q1"]),
    }
    base.update(over)
    return base


QUOTES = {"Q1": {"pass": True, "paragraph": "1", "cited_text": "Brown v Green [2025] FCA 12"},
          "Q2": {"pass": True, "paragraph": "2", "cited_text": "No such case exists. It is fictitious."},
          "Q3": {"pass": True, "paragraph": "3", "cited_text": "I refer the matter"}}
META = {"mnc_from_document": "[2025] FCA 12", "family_law_proposed": "False", "copy_source_markers": "AustLII"}
CHARLOTIN = {"Party(ies)": "Lawyer", "Outcome": "Bar Referral", "Professional Sanction": ""}


def failed(res):
    return {name for name, ok, _ in res if not ok}


def test_clean_row_passes_every_check():
    assert failed(check_row(fields(), QUOTES, doc(), META, CHARLOTIN, [])) == set()


def test_certificate_count_read():
    assert certified_paragraphs(doc()) == 3


def test_invented_citation_text_is_flagged():
    bad = fields(impugned_citations=[{"citation_verbatim": "Smith v Jones [2021] HCA 100",
                                      "characterisation": "non_existent", "asserted_by": "court",
                                      "quote_ids": ["Q2"]}])
    assert "impugned_citation_copied_exactly" in failed(check_row(bad, QUOTES, doc(), META, CHARLOTIN, []))


def test_characterisation_without_cue_is_flagged():
    bad = fields(impugned_citations=[{"citation_verbatim": "Smith v Jones [2020] HCA 99",
                                      "characterisation": "false_quote", "asserted_by": "court",
                                      "quote_ids": ["Q2"]}])
    assert "characterisation_has_textual_cue" in failed(check_row(bad, QUOTES, doc(), META, CHARLOTIN, []))


def test_mnc_title_party_and_referral_disagreements_flagged():
    bad = fields(mnc=f("[2025] FCA 13", ["Q1"]), title_as_published=f("Brown v Greene", ["Q1"]),
                 party_type=f("self_represented", ["Q2"]), regulator_referred=f("", []))
    names = failed(check_row(bad, QUOTES, doc(), META, CHARLOTIN, []))
    assert {"mnc_matches_document_header", "title_found_in_judgment", "party_type_agrees_with_charlotin",
            "referral_agrees_with_charlotin"} <= names


def test_failed_quote_and_dropped_values_flagged():
    q = dict(QUOTES, Q3={"pass": False, "paragraph": "", "cited_text": "x"})
    names = failed(check_row(fields(), q, doc(), META, CHARLOTIN, ["ai_tool_if_stated"]))
    assert {"quotes_found_in_judgment", "no_unsupported_values_dropped"} <= names


def test_family_law_and_wikisource_flags():
    meta = dict(META, family_law_proposed="True", copy_source_markers="Wikisource")
    names = failed(check_row(fields(), QUOTES, doc(), meta, CHARLOTIN, []))
    assert {"family_law_agrees_with_court_code", "official_copy"} <= names


def test_cohen_kappa():
    assert cohen_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == 1.0
    assert round(cohen_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"]), 6) == 0.0
    assert cohen_kappa([], []) is None


def test_party_contention_flagged():
    bad = fields(impugned_citations=[{"citation_verbatim": "Smith v Jones [2020] HCA 99",
                                      "characterisation": "non_existent", "asserted_by": "party",
                                      "quote_ids": ["Q2"]}])
    assert "impugned_by_the_court_itself" in failed(check_row(bad, QUOTES, doc(), META, CHARLOTIN, []))


def test_header_quotes_need_no_paragraph():
    q = dict(QUOTES, Q1={"pass": True, "paragraph": "", "cited_text": "Brown v Green [2025] FCA 12"})
    assert "quotes_have_paragraph_numbers" not in failed(check_row(fields(), q, doc(), META, CHARLOTIN, []))


def test_leading_zero_mnc_is_same_decision():
    from aic.verify import same_mnc
    assert same_mnc("[2025] QIRC 046", "[2025] QIRC 46") and not same_mnc("[2025] QIRC 46", "[2025] QIRC 47")


def test_non_existent_without_listed_citations_is_consistent():
    # The court said the cases do not exist but did not reproduce them.
    ok = fields(impugned_citations=[])
    assert "error_types_consistent" not in failed(check_row(ok, QUOTES, doc(), META, CHARLOTIN, []))


def test_quote_dicts_keep_pass_column():
    # Regression: itertuples() renamed the "pass" column, failing every row.
    import pandas as pd
    qc = pd.DataFrame([{"quote_id": "Q1", "pass": True, "paragraph": "1", "cited_text": "x"}])
    assert qc.to_dict("records")[0]["pass"] is True


def test_title_across_cover_page_layout():
    from aic.verify import title_in_text
    d = Doc([Line(1, "ALEX EXAMPLE Applicant", 72, 12), Line(1, "v", 72, 12),
             Line(1, "SAMPLE INSTITUTE OF TECHNOLOGY Respondent", 72, 12)], 1)
    assert title_in_text("ALEX EXAMPLE v SAMPLE INSTITUTE OF TECHNOLOGY", d)
    assert not title_in_text("ALEX EXAMPLE v SAMPLE UNIVERSITY", d)  # a word not in the judgment


def test_unbracketed_mnc_same_decision():
    from aic.verify import same_mnc
    assert same_mnc("2025 ATMO 264", "[2025] ATMO 264")
    assert not same_mnc("[2025] QIR\n141", "[2025] QIRC 121")
