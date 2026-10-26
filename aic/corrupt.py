"""Synthetic corruptions of real case citations, for the CiteCheck AU evaluation.

Committed before any matcher code exists (brief, R2 "Evaluation"): the generator is fixed
first, so the matcher cannot be shaped around it. Every choice comes from the seeded
random.Random the caller passes in, so the same inputs and seed give the same items.

Each corruption takes one real citation as a judge wrote it (parties plus a medium neutral
citation, or parties plus a law report citation) and changes one thing. Types:

  Medium neutral citations (MNC)
    wrong_number         the number of another case decided by the same court that year
    number_in_range      a number inside the court-year's range with no decision (a gap)
    number_out_of_range  a number above the court-year's highest number
    wrong_year           the year moved by 1 to 3, court and number kept
    wrong_court          another court code, year and number kept
  Law report citations
    wrong_page           the page moved
    wrong_volume         the volume moved
  Both
    wrong_party          one party replaced by a party from another real case
    other_case_parties   all the parties of another real case

The label is not what the matcher should answer. It is what the corpus says about the
corrupted citation, worked out from the ground truth alone:

  exists_same_parties   the citation still names the case recorded at that citation
  exists_other_parties  a case is recorded at that citation, with different parties
  no_record_in_range    no case at that MNC, though the number is within the court-year's range
  outside_coverage      court not in the corpus, a year after the snapshot, or a number above
                        the court-year's highest
  not_in_report_index   a report series the index covers, but no citing judgment uses this
                        volume and page

Labels are relative to the corpus (current to 10 March 2025), never to the world.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, replace
from typing import Protocol

LABELS = ("exists_same_parties", "exists_other_parties", "no_record_in_range", "outside_coverage",
          "not_in_report_index")
MNC_TYPES = ("wrong_number", "number_in_range", "number_out_of_range", "wrong_year", "wrong_court",
             "wrong_party", "other_case_parties")
REPORT_TYPES = ("wrong_page", "wrong_volume", "wrong_party", "other_case_parties")


@dataclass(frozen=True)
class CaseCite:
    parties: str  # as written, e.g. "Smith v Jones"
    kind: str  # "mnc" or "report"
    year: int
    court: str = ""  # MNC court code, e.g. "NSWSC"
    number: int = 0
    series: str = ""  # report series, e.g. "CLR"
    volume: int = 0  # 0 when the series has no volume number
    page: int = 0
    square: bool = False  # report year in [square] brackets

    def render(self) -> str:
        if self.kind == "mnc":
            return f"{self.parties} [{self.year}] {self.court} {self.number}"
        year = f"[{self.year}]" if self.square else f"({self.year})"
        vol = f" {self.volume}" if self.volume else ""
        return f"{self.parties} {year}{vol} {self.series} {self.page}"


class Ground(Protocol):
    """What the corpus records. Built from the indexes, never from the matcher."""

    def mnc_parties(self, court: str, year: int, number: int) -> str | None: ...

    def mnc_max(self, court: str, year: int) -> int | None:  # None: court-year not in the corpus
        ...

    def report_parties(self, series: str, volume: int, page: int) -> list[str] | None:  # None: never cited
        ...

    def report_series(self) -> set[str]: ...


@dataclass(frozen=True)
class Item:
    corruption: str
    original: str
    corrupted: str
    label: str


_NOISE = re.compile(r"\b(the|pty|ltd|limited|inc|co|corporation|re|ex parte|and|of|for|&|no \d+)\b|[^\w\s]")


def party_key(parties: str) -> frozenset[str]:
    """Order-free set of the words that identify the parties, for deciding the label only."""
    words = _NOISE.sub(" ", parties.lower()).split()
    return frozenset(w for w in words if len(w) > 1)


def same_parties(a: str, b: str) -> bool:
    ka, kb = party_key(a), party_key(b)
    return bool(ka) and ka == kb


def label_for(c: CaseCite, ground: Ground) -> str:
    if c.kind == "mnc":
        top = ground.mnc_max(c.court, c.year)
        if top is None or c.number > top:
            return "outside_coverage"
        recorded = ground.mnc_parties(c.court, c.year, c.number)
        if recorded is None:
            return "no_record_in_range"
        return "exists_same_parties" if same_parties(c.parties, recorded) else "exists_other_parties"
    if c.series not in ground.report_series():
        return "outside_coverage"
    seen = ground.report_parties(c.series, c.volume, c.page)
    if not seen:
        return "not_in_report_index"
    return "exists_same_parties" if any(same_parties(c.parties, s) for s in seen) else "exists_other_parties"


def _sides(parties: str) -> list[str]:
    return [s for s in re.split(r"\s+v\s+", parties) if s.strip()]


def _shift(value: int, step: int, rng: random.Random) -> int:
    """value moved up or down by step, moving up when down would leave 1 or more."""
    down = rng.random() < 0.5 and value - step >= 1
    return value - step if down else value + step


def corrupt(c: CaseCite, kind: str, ground: Ground, rng: random.Random, *, donors: list[str],
            courts: list[str]) -> Item | None:
    """One corrupted copy of c, or None when this corruption cannot be made for c.

    donors: party strings of other real cases (for wrong_party and other_case_parties).
    courts: court codes wrong_court may switch to (covered and uncovered).
    """
    new: CaseCite | None = None
    if kind in ("wrong_number", "number_in_range", "number_out_of_range") and c.kind == "mnc":
        top = ground.mnc_max(c.court, c.year)
        if top is None:
            return None
        if kind == "number_out_of_range":
            new = replace(c, number=top + rng.randint(1, max(10, top // 10)))
        else:
            want = kind == "wrong_number"  # True: a recorded number; False: a gap
            pool = [n for n in range(1, top + 1) if n != c.number
                    and (ground.mnc_parties(c.court, c.year, n) is not None) == want]
            if not pool:
                return None
            new = replace(c, number=rng.choice(pool))
    elif kind == "wrong_year" and c.kind == "mnc":
        new = replace(c, year=c.year + rng.choice([-3, -2, -1, 1, 2, 3]))
    elif kind == "wrong_court" and c.kind == "mnc":
        others = [k for k in courts if k != c.court]
        if not others:
            return None
        new = replace(c, court=rng.choice(others))
    elif kind == "wrong_page" and c.kind == "report":
        new = replace(c, page=_shift(c.page, rng.randint(1, 400), rng))
    elif kind == "wrong_volume" and c.kind == "report" and c.volume:
        new = replace(c, volume=_shift(c.volume, rng.randint(1, 30), rng))
    elif kind in ("wrong_party", "other_case_parties"):
        pool = [d for d in donors if not same_parties(d, c.parties)]
        if not pool:
            return None
        donor = rng.choice(pool)
        if kind == "other_case_parties":
            new = replace(c, parties=donor)
        else:
            sides, donor_sides = _sides(c.parties), _sides(donor)
            if not sides or not donor_sides:
                return None
            i = rng.randrange(len(sides))
            sides[i] = rng.choice(donor_sides)
            new = replace(c, parties=" v ".join(sides))
    if new is None or new == c:
        return None
    return Item(kind, c.render(), new.render(), label_for(new, ground))
