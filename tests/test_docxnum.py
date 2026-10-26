from aic.docxnum import _fmt, _roman


def test_number_formats_match_word_levels():
    assert _fmt(3, "decimal") == "3"
    assert _fmt(1, "lowerLetter") == "a" and _fmt(8, "lowerLetter") == "h"
    assert _fmt(2, "upperLetter") == "B"
    assert _fmt(4, "lowerRoman") == "iv" and _roman(9) == "ix" and _roman(14) == "xiv"
