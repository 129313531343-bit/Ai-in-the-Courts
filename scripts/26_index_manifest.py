"""Checksums and size budget for the CiteCheck indexes (built locally, never committed).

Brief: indexes are gitignored and deployed with the site; commit the build scripts and the
SHA-256 checksums; total size at most 10 MB gzipped. Every index file is already gzipped
(or tiny JSON), so the bytes on disk are the deployed bytes.

Output (committed): data/interim/citecheck_index_manifest.csv  path, bytes, sha256
"""

import csv
import gzip
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402

PUBLIC = ROOT / "citecheck/public"
BUDGET = 10 * 1024 * 1024


def main() -> None:
    files = sorted(p for p in (PUBLIC / "data").rglob("*") if p.is_file())
    with (ROOT / "data/interim/citecheck_index_manifest.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["path", "bytes", "sha256"])
        for p in files:
            w.writerow([p.relative_to(PUBLIC).as_posix(), p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest()])
    gz = sum(p.stat().st_size if p.suffix == ".gz" else len(gzip.compress(p.read_bytes(), 9)) for p in files)
    by_index = {}
    for p in files:
        part = p.relative_to(PUBLIC / "data").parts[0]
        by_index[part] = by_index.get(part, 0) + p.stat().st_size
    print(f"{len(files)} files; gzipped total {gz / 1048576:.2f} MiB of the {BUDGET / 1048576:.0f} MiB budget; "
          + ", ".join(f"({k}) {v / 1048576:.2f} MiB" for k, v in sorted(by_index.items())))
    if gz > BUDGET:
        sys.exit("over the 10 MB budget")


if __name__ == "__main__":
    main()
