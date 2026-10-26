"""Export the court code table to CiteCheck (citecheck/src/core/data/courts.json).

One table serves both releases: data/reference/court_codes.csv. The parser reads any
[year] CODE number form; this table only names the court and its jurisdiction. Which
courts the indexes cover is decided by the corpus, not here.
"""

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402


def main() -> None:
    with (ROOT / "data/reference/court_codes.csv").open(newline="") as f:
        rows = [{"code": r["code"], "name": r["court_name"], "jurisdiction": r["jurisdiction"],
                 "level": r["court_level"]} for r in csv.DictReader(f)]
    out = ROOT / "citecheck/src/core/data/courts.json"
    out.write_text(json.dumps(rows, indent=1) + "\n")
    print(f"{len(rows)} courts -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
