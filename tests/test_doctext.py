from aic.doctext import Doc, Line, load_text, match_quote, paragraph_markers, strip_furniture

BODY, SMALL = 12.0, 9.0


def L(page, text, x0=72.0, size=BODY):  # noqa: N802
    return Line(page, text, x0, size)


def test_running_header_and_page_numbers_removed():
    words = ["alpha", "bravo", "charlie", "delta"]
    lines = []
    for p in range(1, 5):
        lines += [L(p, "Smith v Jones [2025] FCA 1"), L(p, f"{words[p - 1]} text"), L(p, str(p), x0=300)]
    kept = [ln.text for ln in strip_furniture(lines, 4)]
    assert kept == [f"{w} text" for w in words]


def test_paragraph_number_alone_at_edge_survives():
    # A line that is only "7" at the bottom of p1 is a paragraph number, not a page number:
    # the page numbers here are "1".."4" at the top, so offset 0; "7" on p1 has offset 6.
    lines = []
    for p in range(1, 5):
        lines += [L(p, str(p), x0=300), L(p, "text"), L(p, "more")]
    lines.insert(3, L(1, "7"))  # end of page 1
    kept = [ln.text for ln in strip_furniture(lines, 4)]
    assert "7" in kept and "1" not in kept


def test_short_document_left_alone():
    lines = [L(1, "Header"), L(1, "text"), L(2, "Header"), L(2, "text")]
    assert strip_furniture(lines, 2) == lines


def test_paragraph_chain_ignores_footnotes_and_orders():
    lines = [
        L(1, "ORDERS"),
        L(1, "1. The appeal is dismissed."),
        L(1, "2. The appellant pay costs."),
        L(1, "REASONS"),
        L(1, "1 The appellant filed submissions."),
        L(1, "that were prepared using AI.", x0=90),
        L(1, "1 See Practice Note SC Gen 23.", size=SMALL),  # footnote: small font
        L(2, "2 The cases cited do not exist."),
        L(2, "3 I refer the matter.", x0=90 + 40),  # indented: not a paragraph start
        L(2, "3 The respondent did not object."),
        L(2, "4 Costs follow the event."),
    ]
    m = paragraph_markers(lines)
    assert m == {4: 1, 7: 2, 9: 3, 10: 4}


def test_bracketed_paragraph_numbers():
    lines = [L(1, f"[{n}] text {n}") for n in range(1, 6)]
    assert list(paragraph_markers(lines).values()) == [1, 2, 3, 4, 5]


def test_unnumbered_document_has_no_markers():
    lines = [L(1, "Some text"), L(1, "2025 was a year"), L(1, "more")]
    assert paragraph_markers(lines) == {}


def _doc():
    lines = [L(1, "1 The applicant relied on Smith v Jones [2020] HCA 99."),
             L(1, "2 That case does not exist. No such decision"),
             L(2, "was ever delivered by the High Court."),
             L(2, "3 The applicant's solicitor accepted that AI was used.")]
    return Doc(lines, 2)


def test_quote_found_on_cited_page_with_paragraph():
    m = match_quote(_doc(), "That case does not exist.", pages=(1, 1))
    assert m.passed and m.page == 1 and m.paragraph == "2" and m.where == "cited_pages"


def test_quote_spanning_pages_keeps_paragraph():
    m = match_quote(_doc(), "No such decision was ever delivered by the High Court.", pages=(1, 2))
    assert m.passed and m.paragraph == "2"


def test_quote_on_wrong_page_found_elsewhere():
    m = match_quote(_doc(), "The applicant’s solicitor accepted that AI was used.", pages=(1, 1))
    assert m.passed and m.where == "other_pages" and m.paragraph == "3" and m.page == 2


def test_fabricated_quote_fails():
    m = match_quote(_doc(), "The Court found the solicitor acted dishonestly and referred him.", pages=(1, 2))
    assert not m.passed and m.where == "not_found" and m.paragraph == ""


def test_scanned_document_flagged():
    d = Doc([L(1, "x")], 1, scanned=True)
    assert match_quote(d, "anything").where == "scanned"


def test_plain_text_document():
    d = load_text("1 First paragraph.\n\n2 The cited case could not be located.\n3 Third.")
    m = match_quote(d, "The cited case could not be located.")
    assert m.passed and m.paragraph == "2"


def test_austlii_header_block_and_url_footers_removed():
    from aic.doctext import strip_publisher
    lines = [
        L(1, "AustLII"),
        L(1, "Supreme Court of New South Wales"),
        L(1, "Smith v Jones [2026] NSWSC 1 (5 June"),
        L(1, "2026)"),
        L(1, "Last Updated: 5 June 2026"),
        L(1, "Supreme Court"),
        L(1, "1 The plaintiff relied on AI."),
        L(1, "https://www.austlii.edu.au/cgi-bin/viewdoc/au/cases/nsw/NSWSC/2026/1.html?context=1;mask_path"),
        L(2, "2 The cases do not exist."),
        L(2, "https://www.austlii.edu.au/cgi-bin/viewdoc/au/cases/nsw/NSWSC/2026/1.html?context=1;mask_pa..."),
    ]
    kept = [ln.text for ln in strip_publisher(lines)]
    assert kept == ["Supreme Court", "1 The plaintiff relied on AI.", "2 The cases do not exist."]


def test_austlii_footnote_url_in_body_kept():
    from aic.doctext import strip_publisher
    lines = [L(1, f"line {i}") for i in range(8)]
    lines.insert(4, L(1, "[11] https://www.austlii.edu.au/ cited in the body"))
    assert len(strip_publisher(lines)) == 9


def test_wikisource_cover_and_end_matter_removed():
    from aic.doctext import strip_publisher
    lines = [L(1, "Valu v Minister"), L(1, "Exported from Wikisource on May 25, 2025"),
             L(2, "Valu v Minister [2025] FedCFamC2G 95"), L(2, "1 The applicant."),
             L(3, "2 The citations did not exist."),
             L(4, "This e-book comes from the online library Wikisource. This"), L(4, "Contributors")]
    kept = [ln.text for ln in strip_publisher(lines)]
    assert kept == ["Valu v Minister [2025] FedCFamC2G 95", "1 The applicant.", "2 The citations did not exist."]


def test_doc_text_uses_newlines_and_offsets_match_flat():
    d = Doc([L(1, "alpha beta"), L(1, "gamma")], 1)
    assert d.text == "alpha beta\ngamma" and d.flat == "alpha beta gamma"
    assert d.text[d.starts[1]:] == "gamma"


def test_front_matter_location():
    d = Doc([L(1, "ORDERS"), L(1, "The applicant's lawyer personally pay costs."), L(1, "REASONS"),
             L(1, "1 The applicant cited cases."), L(1, "2 They did not exist."), L(1, "3 Costs.")], 1)
    assert d.location_at(1) == "front_matter" and d.location_at(4) == "" and d.paragraph_at(4) == "2"
    assert Doc([L(1, "no numbers here")], 1).location_at(0) == "unnumbered_document"
