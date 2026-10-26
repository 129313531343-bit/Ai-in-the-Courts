import random

from aic.corrupt import LABELS, MNC_TYPES, REPORT_TYPES, CaseCite, corrupt, label_for, same_parties


class FakeGround:
    """NSWSC 2019 has decisions 1-10 except 4 (a gap); VSC is not in the corpus."""

    def __init__(self):
        self.mnc = {("NSWSC", 2019, n): f"Party{n} v Other{n}" for n in range(1, 11) if n != 4}
        self.mnc[("NSWSC", 2019, 7)] = "Smith v Jones"
        self.mnc[("NSWCA", 2019, 7)] = "Brown v Green"
        self.reports = {("CLR", 175, 1): ["Mabo v Queensland (No 2)"]}  # round series: year not part of the key

    def mnc_parties(self, court, year, number):
        return self.mnc.get((court, year, number))

    def mnc_max(self, court, year):
        nums = [n for (c, y, n) in self.mnc if c == court and y == year]
        return max(nums) if nums else None

    def report_parties(self, series, year, volume, page):
        return self.reports.get((series, volume, page))

    def report_series(self):
        return {"CLR"}


G = FakeGround()
REAL = CaseCite("Smith v Jones", "mnc", 2019, court="NSWSC", number=7)
REPORT = CaseCite("Mabo v Queensland (No 2)", "report", 1992, series="CLR", volume=175, page=1)
DONORS = ["Party2 v Other2", "Brown v Green", "Taylor v Wilson"]


def make(kind, c=REAL, seed=1, courts=("NSWSC", "NSWCA", "VSC")):
    return corrupt(c, kind, G, random.Random(seed), donors=DONORS, courts=list(courts))


def test_render():
    assert REAL.render() == "Smith v Jones [2019] NSWSC 7"
    assert REPORT.render() == "Mabo v Queensland (No 2) (1992) 175 CLR 1"
    qdr = CaseCite("A v B", "report", 1990, series="Qd R", volume=1, page=5, square=True)
    assert qdr.render() == "A v B [1990] 1 Qd R 5"


def test_real_citation_label():
    assert label_for(REAL, G) == "exists_same_parties"


def test_wrong_number_points_at_another_recorded_case():
    item = make("wrong_number")
    assert item.label == "exists_other_parties" and "[2019] NSWSC 7" not in item.corrupted


def test_number_in_range_is_the_gap():
    item = make("number_in_range")
    assert item.corrupted == "Smith v Jones [2019] NSWSC 4" and item.label == "no_record_in_range"


def test_number_out_of_range():
    item = make("number_out_of_range")
    assert item.label == "outside_coverage" and int(item.corrupted.rsplit(" ", 1)[1]) > 10


def test_wrong_year_and_court_are_labelled_from_the_ground():
    for seed in range(20):
        y = make("wrong_year", seed=seed)
        assert y.label == "outside_coverage"  # no other NSWSC year exists in the fixture
        c = make("wrong_court", seed=seed)
        assert c.label == ("exists_other_parties" if "NSWCA" in c.corrupted else "outside_coverage")


def test_party_corruptions():
    assert make("other_case_parties").label == "exists_other_parties"
    item = make("wrong_party")
    assert item.label == "exists_other_parties" and item.corrupted != REAL.render()


def test_report_corruptions():
    page = make("wrong_page", c=REPORT)
    assert page.label == "not_in_report_index"
    assert make("other_case_parties", c=REPORT).label == "exists_other_parties"
    assert label_for(CaseCite("A v B", "report", 1990, series="NSWLR", volume=20, page=1), G) == "outside_coverage"


def test_impossible_corruptions_return_none():
    assert make("wrong_number", c=CaseCite("A v B", "mnc", 2019, court="VSC", number=3)) is None
    assert make("wrong_year", c=REPORT) is None
    assert make("wrong_volume", c=CaseCite("A v B", "report", 1990, series="CLR", page=3)) is None


def test_deterministic_for_a_seed():
    for kind in MNC_TYPES:
        assert make(kind, seed=42) == make(kind, seed=42)
    for kind in REPORT_TYPES:
        assert make(kind, c=REPORT, seed=7) == make(kind, c=REPORT, seed=7)


def test_labels_are_from_the_documented_set():
    for kind in MNC_TYPES:
        for seed in range(10):
            item = make(kind, seed=seed)
            assert item is None or item.label in LABELS


def test_same_parties_ignores_order_case_and_company_words():
    assert same_parties("Smith v Jones Pty Ltd", "JONES PTY LIMITED v SMITH")
    assert not same_parties("Smith v Jones", "Smith v Brown")
    assert not same_parties("", "")


def test_real_report_label():
    assert label_for(REPORT, G) == "exists_same_parties"
