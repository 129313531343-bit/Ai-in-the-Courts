"""Index (a): medium neutral citation -> date, official URL and party fingerprints.

Built from corpus metadata (cache/corpus/decisions.csv.gz, written by 21_corpus_scan.py).
One gzipped JSON file per court-year, which the site loads only when a citation needs it:

  citecheck/public/data/a/<COURT>/<YEAR>.json.gz
    {"court": "NSWSC", "year": 2019, "max": 1918, "gap": 0.0193, "src": "nsw_caselaw",
     "r": {"123": ["2019-05-03", "<url tail>", "<fingerprints>"]}}
  citecheck/public/data/a/index.json   every court-year: decisions, highest number, gap rate

URL tails drop a per-source prefix (URL_PREFIX) to save space. Fingerprints are
aic.fingerprint.encode_title: no readable names are written (DECISIONS.md D031, E1).
Codes not in data/reference/court_codes.csv (about 30 garbled ones, D032) are left out.

The files are gitignored and deployed with the site; scripts/26_index_manifest.py records
their SHA-256 checksums in a committed manifest.
"""

import csv
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402
from aic.courts import courts  # noqa: E402
from aic.fingerprint import encode_title  # noqa: E402

OUT = ROOT / "citecheck/public/data/a"
URL_PREFIX = {
    "nsw_caselaw": "https://www.caselaw.nsw.gov.au/decision/",
    "federal_court_of_australia": "https://www.judgments.fedcourt.gov.au/judgments/Judgments/",
    "high_court_of_australia": "https://eresources.hcourt.gov.au/",
}


def write_gz(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode()
    path.write_bytes(gzip.compress(data, compresslevel=9, mtime=0))


def main() -> None:
    known = set(courts())
    groups: dict[tuple[str, int], list[dict]] = defaultdict(list)
    skipped = 0
    with gzip.open(ROOT / "cache/corpus/decisions.csv.gz", "rt", newline="") as f:
        for r in csv.DictReader(f):
            if r["court"] not in known:
                skipped += 1
                continue
            groups[(r["court"], int(r["year"]))].append(r)
    index = []
    full_urls = 0
    for (court, year), rows in sorted(groups.items()):
        srcs = {r["source"] for r in rows}
        src = srcs.pop() if len(srcs) == 1 else ""
        recs = {}
        for r in rows:
            prefix = URL_PREFIX.get(r["source"], "")
            tail = r["url"][len(prefix):] if src and prefix and r["url"].startswith(prefix) else r["url"]
            full_urls += tail == r["url"]
            recs[r["number"]] = [r["date"], tail, encode_title(r["title"])]
        top = max(int(n) for n in recs)
        gap = round(1 - len(recs) / top, 4)
        write_gz(OUT / court / f"{year}.json.gz",
                 {"court": court, "year": year, "max": top, "gap": gap, "src": src, "r": recs})
        index.append({"court": court, "year": year, "n": len(recs), "max": top, "gap": gap, "src": src})
    (OUT / "index.json").write_text(json.dumps({"as_at": "2025-03-10", "url_prefix": URL_PREFIX,
                                                "court_years": index}, separators=(",", ":")) + "\n")
    total = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"index (a): {len(index)} court-years, {sum(x['n'] for x in index):,} decisions, "
          f"{skipped} with unknown codes skipped, {full_urls} full URLs kept; {total / 1e6:.2f} MB on disk")


if __name__ == "__main__":
    main()
