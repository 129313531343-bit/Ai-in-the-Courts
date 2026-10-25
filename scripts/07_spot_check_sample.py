"""Draw Luc's 10 random spot-check rows, before any extraction results exist.

Pre-registered: the sample is drawn and committed before Pass A/B run, so it
cannot be chosen to look good. The population is every row whose judgment has
a text layer (so it can be verified automatically), minus the Pass A
development sample: prompts may be tuned on those rows, so their accuracy
would be biased upwards.

Rows flagged by the automatic verifier are reviewed in addition to these 10.
Accuracy is estimated from these 10 only, because flagged rows are not a
random sample.

Output: data/review/spot_check_sample.csv (refuses to overwrite).
"""

import random
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402

SEED = 20261031  # R1 due date; any fixed value would do, what matters is that it was fixed in advance
N = 10


def main() -> None:
    out = ROOT / "data/review/spot_check_sample.csv"
    if out.exists():
        sys.exit(f"{out} already exists; the pre-registered sample must not be redrawn.")
    meta = pd.read_csv(ROOT / "data/interim/doc_metadata.csv", dtype=str, keep_default_na=False)
    dev = set(pd.read_csv(ROOT / "data/interim/pass_a/dev_sample.csv", dtype=str).charlotin_row)
    pool = sorted(meta[(meta.scanned != "True") & ~meta.charlotin_row.isin(dev)].charlotin_row, key=int)
    picks = sorted(random.Random(SEED).sample(pool, N), key=int)
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"charlotin_row": picks, "seed": SEED, "population_size": len(pool),
                  "drawn_on": date.today().isoformat()}).to_csv(out, index=False)
    print(f"drew {N} of {len(pool)} rows (seed {SEED}): {', '.join(picks)}")


if __name__ == "__main__":
    main()
