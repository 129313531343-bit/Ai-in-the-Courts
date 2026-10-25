from aic.textnorm import join_lines, norm_line, norm_passage


def test_ligatures_expand():
    assert norm_line("signiﬁcant ﬂaw") == "significant flaw"


def test_curly_quotes_and_dashes():
    assert norm_line("“false” ‘case’ – —") == "\"false\" 'case' - -"


def test_whitespace_and_invisible_characters():
    assert norm_line("  non­existent  \t case​ ") == "nonexistent case"


def test_dehyphenation_across_lines():
    text, starts = join_lines(["the authority does not exis-", "t and was fabricated"])
    assert text == "the authority does not exist and was fabricated"
    assert starts == [0, 27]


def test_hyphen_kept_before_capital():
    # "Smith-" + "Jones" is probably a hyphenated name, not a broken word.
    text, _ = join_lines(["Smith-", "Jones"])
    assert text == "Smith- Jones"


def test_line_starts_track_offsets():
    text, starts = join_lines(["alpha", "beta", "gamma"])
    assert [text[s:s + 4] for s in starts] == ["alph", "beta", "gamm"]


def test_norm_passage_multiline():
    assert norm_passage("The  applicant’s\n  submissions were  prepa-\nred with AI.\n") == \
        "The applicant's submissions were prepared with AI."
