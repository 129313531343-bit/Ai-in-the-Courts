"""Download the judgments Charlotin hosts for Australian rows, 1 request every 5 s.

Only /documents/ links on damiencharlotin.com are fetched. AustLII, NSW Caselaw,
Westlaw and media links are never fetched in code (AustLII and NSW Caselaw
exclude robots; the others are not judgments). Those are left for a person.

Files go to cache/docs/ (gitignored: judgment text is never committed).
The manifest with SHA-256 hashes, data/interim/doc_manifest.csv, is committed
so anyone can check they have the same files. Re-running skips files already
fetched.
"""

import csv
import hashlib
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache/docs"
MANIFEST = ROOT / "data/interim/doc_manifest.csv"
DELAY_S = 5
UA = "ai-in-courts/0.1 (personal non-commercial research project; 1 request per 5 s)"
FIELDS = ["charlotin_row", "url", "status", "content_type", "bytes", "sha256", "local_file", "fetched_at_utc"]


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    cases = pd.read_csv(ROOT / "data/interim/au_cases.csv", dtype=str, keep_default_na=False)
    todo = cases[cases.source_kind == "charlotin_document"]

    done = {}
    if MANIFEST.exists():
        done = {r["charlotin_row"]: r for r in csv.DictReader(MANIFEST.open())}
    rows = [r for r in done.values()]

    session = requests.Session()
    session.headers["User-Agent"] = UA
    first = True
    for _, c in todo.iterrows():
        key = c.charlotin_row
        if key in done and done[key]["status"] == "200":
            continue
        if not first:
            time.sleep(DELAY_S)
        first = False
        url = c.source_url
        ext = Path(url).suffix.lower() or ".bin"
        try:
            r = session.get(url, timeout=60)
            status, body, ctype = str(r.status_code), r.content, r.headers.get("Content-Type", "")
        except requests.RequestException as e:
            status, body, ctype = f"error:{type(e).__name__}", b"", ""
        sha = hashlib.sha256(body).hexdigest() if body else ""
        local = ""
        if status == "200" and body:
            local = f"{key}_{sha[:12]}{ext}"
            (CACHE / local).write_bytes(body)
        row = dict(charlotin_row=key, url=url, status=status, content_type=ctype, bytes=len(body),
                   sha256=sha, local_file=local,
                   fetched_at_utc=datetime.now(UTC).isoformat(timespec="seconds"))
        rows = [x for x in rows if x["charlotin_row"] != key] + [row]
        print(key, status, len(body), ext, flush=True)
        with MANIFEST.open("w", newline="") as f:  # rewrite each time so a crash loses nothing
            w = csv.DictWriter(f, FIELDS)
            w.writeheader()
            w.writerows(sorted(rows, key=lambda x: int(x["charlotin_row"])))

    ok = sum(1 for x in rows if x["status"] == "200")
    print(f"done: {ok}/{len(todo)} fetched")


if __name__ == "__main__":
    main()
