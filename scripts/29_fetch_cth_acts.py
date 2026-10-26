"""Index (d): every Commonwealth Act on the Federal Register, with its former names and status.

The Federal Register API cannot filter on former names (the nameHistory query fails server
side, tested 26 Oct 2026), so the site cannot look up "Trade Practices Act 1974" live. This
script downloads the title list once (13,747 Acts in force and repealed, 26 Oct 2026), in
pages of 500 (the API's limit), one request every 10 s (the Crawl-delay www.legislation.gov.au sets; the API
host publishes no robots.txt). The site then resolves titles, former names and repeal
locally, and asks the API only for the Act's current text, to check section numbers.

Output:
  cache/legislation/cth_acts_raw.json           the API's records (gitignored)
  citecheck/public/data/d/cth_acts.json.gz      [{"i": id, "n": name, "y": year, "f": in force 1/0,
                                                  "s": status, "h": [former names]}]  (deployed)
Federal Register of Legislation material is CC BY 4.0 (attribution on the site).
"""

import gzip
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402

API = "https://api.prod.legislation.gov.au/v1/titles"
PAGE = 500  # the API rejects larger pages ("limit of 500 for Top")
DELAY_S = 10
UA = "ai-in-courts/0.1 (personal non-commercial research project; 1 request per 10 s)"


def main() -> None:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    records, skip, total = [], 0, None
    while total is None or skip < total:
        if skip:
            time.sleep(DELAY_S)
        r = s.get(API, params={"$filter": "collection eq 'Act'", "$count": "true", "$orderby": "id",
                               "$top": PAGE, "$skip": skip,
                               "$select": "id,name,year,number,isInForce,status,nameHistory"}, timeout=120)
        r.raise_for_status()
        body = r.json()
        total = body["@odata.count"]
        records += body["value"]
        skip += PAGE
        print(f"{len(records):,} of {total:,}", flush=True)
    raw = ROOT / "cache/legislation/cth_acts_raw.json"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text(json.dumps({"fetched_at_utc": datetime.now(UTC).isoformat(timespec="seconds"), "count": total,
                               "records": records}))
    out = []
    for a in records:
        former = [h["name"] for h in (a.get("nameHistory") or []) if h["name"] != a["name"]]
        out.append({"i": a["id"], "n": a["name"], "y": a.get("year"), "f": int(bool(a.get("isInForce"))),
                    "s": a.get("status") or "", "h": former})
    path = ROOT / "citecheck/public/data/d/cth_acts.json.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(json.dumps(out, separators=(",", ":"), ensure_ascii=False).encode(), 9, mtime=0))
    print(f"index (d): {len(out):,} Acts ({sum(a['f'] for a in out):,} in force, "
          f"{sum(1 for a in out if a['h']):,} with former names); {path.stat().st_size / 1e3:.0f} kB")


if __name__ == "__main__":
    main()
