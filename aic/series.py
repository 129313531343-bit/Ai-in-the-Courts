"""Law report series, read from the table the CiteCheck parser uses (citecheck/src/core/data/series.json)."""

import json
from functools import cache

from aic import ROOT


@cache
def square_series() -> frozenset[str]:
    """Series whose volumes run within a year, so the year is part of a report's identity."""
    data = json.loads((ROOT / "citecheck/src/core/data/series.json").read_text())
    return frozenset(s["abbr"] for s in data if s["style"] == "square")


def report_key(series: str, year: int, volume: int | None, page: int) -> str:
    """Same as reportKey() in citecheck/src/core/series.ts: "volume|page" or "year/volume|page"."""
    vol = volume or ""
    return f"{year}/{vol}|{page}" if series in square_series() else f"{vol}|{page}"
