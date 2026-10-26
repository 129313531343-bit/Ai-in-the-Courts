"""Index (b): law report citation -> party fingerprints and how many judgments cite it.

From cache/corpus/reports_raw.json (written by citecheck/scripts/mine_reports.ts, which skips
the evaluation sources). Only citations made by at least 2 judgments are kept (brief): a
citation seen once may itself be a typo. For each, the year most often written and up to
three of the commonest ways judgments name the parties, as fingerprints only (D031, E1).

Output (gitignored, deployed), one gzipped file per series:
  citecheck/public/data/b/<SERIESKEY>.json.gz  {"series": "CLR", "r": {"175|1": [n, year, ["fp fp|fp", ...]]}}
  (keys are reportKey(): "volume|page", or "year/volume|page" for square-bracket series such as Qd R)
  citecheck/public/data/b/index.json           every series: citations kept, judgments cited
SERIESKEY is the series without spaces or full stops, upper case ("Qd R" -> "QDR"), as in
citecheck/src/core/series.ts seriesKey(). Checksums: scripts/26_index_manifest.py.
"""

import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402

OUT = ROOT / "citecheck/public/data/b"
MIN_CITING = 2
VARIANTS = 3


def series_key(abbr: str) -> str:
    return abbr.replace(" ", "").replace(".", "").upper()


def main() -> None:
    raw = json.loads((ROOT / "cache/corpus/reports_raw.json").read_text())
    shards: dict[str, dict] = defaultdict(dict)
    names: dict[str, str] = {}
    for key, e in raw.items():
        if e["n"] < MIN_CITING:
            continue
        series, within = key.split("|", 1)  # within: reportKey, "vol|page" or "year/vol|page"
        year = max(e["years"].items(), key=lambda kv: (kv[1], kv[0]))[0]
        top = [enc for enc, _ in sorted(e["parties"].items(), key=lambda kv: -kv[1])[:VARIANTS]]
        shards[series_key(series)][within] = [e["n"], int(year), top]
        names[series_key(series)] = series
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.json.gz"):
        old.unlink()
    summary = []
    for key, recs in sorted(shards.items()):
        data = json.dumps({"series": names[key], "r": recs}, separators=(",", ":")).encode()
        (OUT / f"{key}.json.gz").write_bytes(gzip.compress(data, 9, mtime=0))
        summary.append({"series": names[key], "key": key, "citations": len(recs),
                        "citing_max": max(v[0] for v in recs.values())})
    (OUT / "index.json").write_text(json.dumps({"min_citing": MIN_CITING, "series": summary},
                                               separators=(",", ":")) + "\n")
    size = sum(p.stat().st_size for p in OUT.iterdir())
    print(f"index (b): {sum(s['citations'] for s in summary):,} citations in {len(summary)} series; "
          f"{size / 1e6:.2f} MB on disk")
    for s in sorted(summary, key=lambda s: -s["citations"]):
        print(f"  {s['series']:<10} {s['citations']:>7,}")


if __name__ == "__main__":
    main()
