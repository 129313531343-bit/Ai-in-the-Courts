"""Write name-free manifests that can be published instead of files containing names.

Privacy decision C1 (PRIVACY.md): Charlotin's CSVs, the case list and the
download manifest (whose URLs contain case names) stay on this Mac. The
public repo gets enough to verify that anyone else has the identical files:
  raw/SHA256SUMS.txt          SHA-256 of each raw Charlotin download (re-download from Charlotin's site)
  data/interim/doc_hashes.csv per tracker row: SHA-256, size and fetch time of the judgment copy
"""

import hashlib
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402


def main() -> None:
    lines = []
    for p in sorted((ROOT / "raw").glob("*.csv")):
        lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}")
    (ROOT / "raw/SHA256SUMS.txt").write_text(
        "# SHA-256 of Charlotin's AI Hallucination Cases CSV as downloaded, and its Australian subset.\n"
        "# Source: https://www.damiencharlotin.com/hallucinations/hallucinations/download.csv (CC BY 4.0).\n"
        "# The files are not committed (they name self-represented litigants; see PRIVACY.md, decision C1).\n"
        + "\n".join(lines) + "\n")
    man = pd.read_csv(ROOT / "data/interim/doc_manifest.csv", dtype=str, keep_default_na=False)
    man["charlotin_document_id"] = man.url.str.extract(r"/documents/(\d+)/", expand=False)
    man["file_type"] = man.local_file.str.rsplit(".", n=1).str[-1]
    man[["charlotin_row", "charlotin_document_id", "file_type", "bytes", "sha256", "fetched_at_utc"]].to_csv(
        ROOT / "data/interim/doc_hashes.csv", index=False)
    print(f"wrote raw/SHA256SUMS.txt ({len(lines)} files) and data/interim/doc_hashes.csv ({len(man)} rows)")


if __name__ == "__main__":
    main()
