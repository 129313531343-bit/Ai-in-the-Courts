"""Scan the Open Australian Legal Corpus once and keep only metadata (no document text).

Input:  cache/corpus/corpus.jsonl (v7.1.0, pinned in DECISIONS.md D029; streamed line by line)
Output (gitignored, they hold case titles):
  cache/corpus/decisions.csv.gz    version_id, source, court, year, number, title, date, url, chars
  cache/corpus/legislation.csv.gz  version_id, type, source, jurisdiction, title, url
Output (committed, counts only):
  data/interim/corpus_court_years.csv  court, year, decisions, max_number, gap_rate
  data/interim/corpus_summary.json     totals, duplicates, decisions without an MNC, unknown court codes

Gap rate: 1 - (distinct numbers recorded) / (highest number). A court-year with numbers
1..200 and 180 decisions recorded has a gap rate of 0.10, so about one number in ten has no
decision in the corpus (unpublished, restricted or missing).
"""

import csv
import gzip
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402
from aic.courts import courts  # noqa: E402

CORPUS = ROOT / "cache/corpus/corpus.jsonl"
TITLE_MNC = re.compile(r"^(.*?)\s*\[\s*(\d{4})\s*\]\s+([A-Za-z][A-Za-z0-9]{1,15})\s+(\d{1,6})\s*$")


def main() -> None:
    dec_out = gzip.open(ROOT / "cache/corpus/decisions.csv.gz", "wt", newline="")
    leg_out = gzip.open(ROOT / "cache/corpus/legislation.csv.gz", "wt", newline="")
    dw = csv.writer(dec_out)
    lw = csv.writer(leg_out)
    dw.writerow(["version_id", "source", "court", "year", "number", "title", "date", "url", "chars"])
    lw.writerow(["version_id", "type", "source", "jurisdiction", "title", "url"])
    numbers: dict[tuple[str, int], set[int]] = defaultdict(set)
    seen: set[tuple[str, int, int]] = set()
    counts = Counter()
    no_mnc = Counter()
    dupes = 0
    with CORPUS.open("rb") as f:
        for i, line in enumerate(f, 1):
            d = json.loads(line)
            counts[(d["type"], d["source"])] += 1
            if d["type"] != "decision":
                lw.writerow([d["version_id"], d["type"], d["source"], d["jurisdiction"], d["citation"], d["url"]])
                continue
            m = TITLE_MNC.match(d["citation"] or "")
            if not m:
                no_mnc[d["source"]] += 1
                continue
            title, year, court, number = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
            key = (court, year, number)
            if key in seen:
                dupes += 1
                continue
            seen.add(key)
            numbers[(court, year)].add(number)
            dw.writerow([d["version_id"], d["source"], court, year, number, title, d["date"] or "", d["url"],
                         len(d["text"] or "")])
            if i % 50000 == 0:
                print(f"{i:,} lines", flush=True)
    dec_out.close()
    leg_out.close()

    rows = []
    for (court, year), nums in sorted(numbers.items()):
        top = max(nums)
        rows.append({"court": court, "year": year, "decisions": len(nums), "max_number": top,
                     "gap_rate": round(1 - len(nums) / top, 4)})
    with (ROOT / "data/interim/corpus_court_years.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    known = set(courts())
    by_court = Counter()
    for (court, _), nums in numbers.items():
        by_court[court] += len(nums)
    summary = {
        "documents": sum(counts.values()),
        "by_type_and_source": {f"{t}/{s}": n for (t, s), n in sorted(counts.items())},
        "decisions_with_mnc": len(seen),
        "duplicate_mnc_skipped": dupes,
        "decisions_without_mnc_in_title": dict(no_mnc),
        "courts": dict(by_court.most_common()),
        "court_codes_not_in_table": sorted(c for c in by_court if c not in known),
    }
    (ROOT / "data/interim/corpus_summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "courts"}, indent=1))


if __name__ == "__main__":
    main()
