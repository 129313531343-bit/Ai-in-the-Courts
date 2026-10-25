from aic.courts import FAMILY_LAW_CODES, courts, find_mnc, format_mnc, own_mnc


def test_table_loads_with_levels():
    c = courts()
    assert c["VSCA"].level == "superior" and c["FWC"].level == "tribunal"
    assert c["FedCFamC2G"].jurisdiction == "Cth"


def test_find_mnc_in_name_and_filename():
    assert find_mnc("Example & Anor v Sample Pty Ltd (No 2) [2026] VBAB 33") == ("2026", "VBAB", "33")
    assert find_mnc("/documents/9999/Example_v_Sample_2026_FedCFamC2G_1245_1_July_2026.pdf") == \
        ("2026", "FedCFamC2G", "1245")


def test_unknown_code_ignored():
    assert find_mnc("[2025] ZZZZ 12") is None


def test_own_mnc_skips_cited_case_from_other_year():
    text = "Cases cited: Smith v Jones [2019] HCA 4\nCitation: Brown v Green [2025] FCA 1234"
    assert own_mnc(text, "2025") == ("2025", "FCA", "1234")


def test_format_strips_leading_zeros():
    assert format_mnc("2025", "NSWSC", "0042") == "[2025] NSWSC 42"


def test_family_law_codes_exclude_general_federal():
    assert "FedCFamC2F" in FAMILY_LAW_CODES and "FedCFamC2G" not in FAMILY_LAW_CODES


def test_own_mnc_tolerates_header_quirks():
    assert own_mnc("MEDIUM NEUTRAL CITATION: [ 2024] VSCA 264", "2024") == ("2024", "VSCA", "264")
    assert own_mnc("DELEGATE: X\nDECISION: 2025 ATMO 264\nCatchwords", "2025") == ("2025", "ATMO", "264")


def test_unlabelled_unbracketed_number_not_taken():
    assert own_mnc("Trade Marks Act 1995 ATMO 264", "1995") is None
