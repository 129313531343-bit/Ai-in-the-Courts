import importlib.util

from aic import ROOT

_spec = importlib.util.spec_from_file_location("build_eval", ROOT / "scripts/27_build_eval.py")
build_eval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_eval)
OWN = ("NSWSC", 2021, 99)


def found(text):
    return [(c["kind"], c["citation"], c["parties"], c["authority"]) for c in build_eval.extract(text, OWN)]


def test_report_with_parties_and_pinpoint():
    assert found("As held in House v The King (1936) 55 CLR 499 at 504-505, x.") == [
        ("report", "House v The King (1936) 55 CLR 499 at 504-505", "House v The King", "CLR|55|499")]


def test_mnc_with_parties_and_pinpoint():
    assert found("See also Smith v Jones [2019] NSWSC 123 at [45]; and more.") == [
        ("mnc", "Smith v Jones [2019] NSWSC 123 at [45]", "Smith v Jones", "NSWSC|2019|123")]


def test_re_ex_parte_and_no_2():
    got = found("x. Re Wakim; Ex parte McNally (1999) 198 CLR 511. Mabo v Queensland (No 2) (1992) 175 CLR 1, 15.")
    assert [g[2] for g in got] == ["Re Wakim; Ex parte McNally", "Mabo v Queensland (No 2)"]


def test_year_only_series_is_a_report_not_an_mnc():
    assert found("Donoghue v Stevenson [1932] AC 562 applies.") == [
        ("report", "Donoghue v Stevenson [1932] AC 562", "Donoghue v Stevenson", "AC|1932/|562")]


def test_bare_citation_has_no_parties():
    assert found("The plaintiff relied on [2020] FCA 12.") == [("mnc", "[2020] FCA 12", "", "FCA|2020|12")]


def test_the_judgment_s_own_citation_is_skipped():
    assert found("This decision: [2021] NSWSC 99.") == []


def test_dates_are_not_reports():
    assert found("It was heard (2019) 12 March 2020.") == []


def test_comma_ends_the_party_name():
    assert found("Brown, Smith v Jones [2018] NSWCA 2.")[0][2] == "Smith v Jones"
