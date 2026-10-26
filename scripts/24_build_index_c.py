"""Index (c): titles of the Acts in force at the corpus snapshot (10 March 2025).

From corpus metadata (cache/corpus/legislation.csv.gz). State Acts (NSW, Qld, WA, SA, Tas)
are what the site checks state statute citations against: no Victorian, ACT or NT Acts are
in the corpus, so those come back "cannot check". Commonwealth Acts are checked live
against the Federal Register; their titles here serve the offline mode only, which cannot
check sections.

Output (gitignored, deployed): citecheck/public/data/c/acts.json.gz
  [{"t": "Civil Liability Act", "y": 2002, "j": "NSW", "x": 0, "u": "<url or register id>"}, ...]
  x = 1 when the source lists the Act as "(Repealed)" (some Tasmanian amending Acts).
Titles with no four-digit year (e.g. "Statute of Frauds (1677) (Imp) (WA)") keep y = null.
"""

import csv
import gzip
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402

JUR = {"commonwealth": "Cth", "norfolk_island": "NI", "new_south_wales": "NSW", "queensland": "Qld",
       "western_australia": "WA", "south_australia": "SA", "tasmania": "Tas"}
TRAIL_JUR = re.compile(r"\s*\((?:Cth|NSW|Qld|WA|SA|Tas|NI|Norfolk Island)\)\s*$")
REPEALED = re.compile(r"\s*\(Repealed\)", re.IGNORECASE)
YEAR = re.compile(r"^(.*?\S)\s+(?:of\s+)?((?:1[6-9]|20)\d\d)\b(.*)$")
CTH_ID = re.compile(r"legislation\.gov\.au/(C\d{4}[AQ]\d{5})/")


def parse_title(raw: str) -> tuple[str, int | None, bool]:
    t = TRAIL_JUR.sub("", raw)
    repealed = bool(REPEALED.search(t))
    t = REPEALED.sub("", t).strip()
    m = YEAR.match(t)
    if not m:
        return t, None, repealed
    title, year, rest = m.group(1), int(m.group(2)), m.group(3).strip()
    if rest.startswith("(No") and not title.endswith(")"):  # "Act 1975 (No 2)" -> keep the number with the title
        title = f"{title} {rest.split(')')[0]})"
    return title, year, repealed


def main() -> None:
    out = []
    with gzip.open(ROOT / "cache/corpus/legislation.csv.gz", "rt", newline="") as f:
        for r in csv.DictReader(f):
            if r["type"] != "primary_legislation":
                continue
            title, year, repealed = parse_title(r["title"])
            cth = CTH_ID.search(r["url"])
            out.append({"t": title, "y": year, "j": JUR[r["jurisdiction"]], "x": int(repealed),
                        "u": cth.group(1) if cth else r["url"]})
    out.sort(key=lambda a: (a["j"], a["t"].lower(), a["y"] or 0))
    path = ROOT / "citecheck/public/data/c/acts.json.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(json.dumps(out, separators=(",", ":"), ensure_ascii=False).encode(), 9, mtime=0))
    by = {}
    for a in out:
        by[a["j"]] = by.get(a["j"], 0) + 1
    print(f"index (c): {len(out)} Acts {by}; {sum(a['y'] is None for a in out)} without a year; "
          f"{sum(a['x'] for a in out)} listed as repealed; {path.stat().st_size / 1e3:.0f} kB")


if __name__ == "__main__":
    main()
