"""Download Charlotin's AI Hallucination Cases CSV into raw/ (unchanged, CC BY 4.0).

The database is updated over time, so a fresh download usually differs from
the snapshot this project used. Release 1 used the 25 October 2026 download,
whose SHA-256 is in raw/SHA256SUMS.txt; this script reports whether the file
you have matches it. The files are gitignored (PRIVACY.md, decision C1).

Usage: python scripts/00_download_charlotin.py [YYYY-MM-DD]   (date used in the filename; default today)
"""

import hashlib
import sys
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402

URL = "https://www.damiencharlotin.com/hallucinations/hallucinations/download.csv"
UA = "ai-in-courts/0.1 (personal non-commercial research project)"


def main() -> None:
    day = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    out = ROOT / f"raw/charlotin_download_{day}.csv"
    if out.exists():
        print(f"{out.name} exists; not downloading again.")
    else:
        r = requests.get(URL, headers={"User-Agent": UA}, timeout=60)
        r.raise_for_status()
        out.write_bytes(r.content)
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    sums = ROOT / "raw/SHA256SUMS.txt"
    known = {line.split()[1]: line.split()[0] for line in sums.read_text().splitlines()
             if line and not line.startswith("#")} if sums.exists() else {}
    status = ("matches the published hash" if known.get(out.name) == sha
              else "differs from the Release 1 snapshot" if known else "no published hash to compare")
    print(f"{out.name}: sha256 {sha} ({status})")


if __name__ == "__main__":
    main()
