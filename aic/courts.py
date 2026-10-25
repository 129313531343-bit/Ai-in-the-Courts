"""Court codes and medium neutral citations (MNCs)."""

import csv
import re
from dataclasses import dataclass
from functools import cache

from aic import ROOT

# "[2025] VSCA 112". Also matches Charlotin's filename form "2026_FedCFamC2G_1245".
MNC_RE = re.compile(r"\[?((?:19|20)\d\d)\]?[ _]+([A-Z][A-Za-z0-9]{1,11})[ _]+(\d{1,5})(?=[ _.,;:)\]]|$)")
# Strict form (square brackets), for reading a judgment's own text. Tolerates
# stray spaces inside the brackets ("[ 2024] VSCA 264", seen in a VSCA header).
MNC_STRICT_RE = re.compile(r"\[\s*((?:19|20)\d\d)\s*\]\s+([A-Z][A-Za-z0-9]{1,11})\s+(\d{1,5})\b")
# A labelled citation in a decision's header, brackets optional ("DECISION: 2025 ATMO 264").
MNC_LABELLED_RE = re.compile(
    r"(?i:medium neutral citation|neutral citation|citation|decision)\s*:\s*"
    r"\[?\s*((?:19|20)\d\d)\s*\]?\s+([A-Z][A-Za-z0-9]{1,11})\s+(\d{1,5})\b")

# Family law divisions, by MNC code. FedCFamC2G is general federal law, not family law.
FAMILY_LAW_CODES = {"FedCFamC1A", "FedCFamC1F", "FedCFamC2F", "FamCA", "FamCAFC", "FCWA", "FCWAM"}


@dataclass(frozen=True)
class Court:
    code: str
    name: str
    jurisdiction: str
    level: str


@cache
def courts() -> dict[str, Court]:
    with (ROOT / "data/reference/court_codes.csv").open(newline="") as f:
        return {r["code"]: Court(r["code"], r["court_name"], r["jurisdiction"], r["court_level"])
                for r in csv.DictReader(f)}


def find_mnc(s: str, strict: bool = False) -> tuple[str, str, str] | None:
    """First (year, code, number) in s whose court code is in our table."""
    for m in (MNC_STRICT_RE if strict else MNC_RE).finditer(s):
        if m.group(2) in courts():
            return m.group(1), m.group(2), m.group(3)
    return None


def format_mnc(year: str, code: str, number: str) -> str:
    return f"[{year}] {code} {int(number)}"


def own_mnc(first_pages_text: str, decision_year: str | None) -> tuple[str, str, str] | None:
    """The decision's own MNC from the top of its text.

    A judgment's own citation normally comes before any cited cases, so the
    first known-court MNC wins, but only if its year matches the decision
    year (a cited case with a different year is skipped). Returns None if
    nothing fits; the reviewer then reads it off the judgment.
    """
    matches = sorted([*MNC_STRICT_RE.finditer(first_pages_text), *MNC_LABELLED_RE.finditer(first_pages_text)],
                     key=lambda m: m.start())
    for m in matches:
        year, code, num = m.groups()
        if code in courts() and (decision_year is None or year == decision_year):
            return year, code, num
    return None
