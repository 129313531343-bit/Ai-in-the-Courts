"""Reserve about 2% of the corpus's judgments as evaluation sources, before any index is mined.

Brief (R2 "Evaluation"): the real citations in the evaluation set come from these judgments,
and index (b), report citations mined from judgment text, must exclude them. Reserving them
first, with a fixed seed, means no later choice can move a document in or out.

Population: every decision in cache/corpus/decisions.csv.gz (decisions with a medium neutral
citation, from the HCA, the Federal Court and NSW Caselaw). Simple random sample without
replacement, seed 20261026, of round(2% of the population) documents.

Output (committed; no titles): eval/eval_sources.csv  version_id, court, year, number
"""

import csv
import gzip
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402

SEED = 20261026
SHARE = 0.02


def main() -> None:
    with gzip.open(ROOT / "cache/corpus/decisions.csv.gz", "rt", newline="") as f:
        rows = sorted(csv.DictReader(f), key=lambda r: r["version_id"])
    k = round(SHARE * len(rows))
    picked = sorted(random.Random(SEED).sample(rows, k), key=lambda r: (r["court"], int(r["year"]), int(r["number"])))
    out = ROOT / "eval/eval_sources.csv"
    out.parent.mkdir(exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["version_id", "court", "year", "number"])
        w.writerows([r["version_id"], r["court"], r["year"], r["number"]] for r in picked)
    print(f"reserved {k:,} of {len(rows):,} decisions (seed {SEED}) -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
