"""Fetch the official AI practice notes and directions used in rules.csv.

Only court and government sites, each checked first for robots.txt rules (none
disallow these files or set AI content signals; checked 25 Oct 2026). One
request every 5 s. Files go to cache/rules/ (not committed); the manifest with
URLs, dates and SHA-256 hashes, data/interim/rules_sources.csv, is committed.

Instruments Luc collects by hand (sites that block bots or need JavaScript)
are not here: the Federal Court, County Court of Victoria, FCFCOA, FWC, ART,
VCAT, QCAT, WA District Court and WA SAT.

Where a court's listing page links a different file from an earlier copy
(possible amendment), both are fetched so they can be compared.
"""

import csv
import hashlib
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402

UA = "ai-in-courts/0.1 (personal non-commercial research project; 1 request per 5 s)"
DELAY_S = 5
NSW = "https://supremecourt.nsw.gov.au/content/dam/dcj/ctsd/supreme-court/documents"
SOURCES = [  # (key, jurisdiction, description, url)
    ("nsw_sc_gen23", "NSW", "Supreme Court of NSW Practice Note SC Gen 23 (current)",
     f"{NSW}/Practice-and-Procedure/Practice-Notes/general/current/PN_SC_Gen_23.pdf"),
    ("nsw_sc_gen23_amendments", "NSW", "SC Gen 23 amendments announcement",
     f"{NSW}/Practice-and-Procedure/Practice-Notes/general/current/PN_SC_Gen_23_announcement.pdf"),
    ("nsw_cj_statement_20251117", "NSW", "Chief Justice's statement: Use of Generative AI - Practice Note Review",
     f"{NSW}/media/Statement-AI-20251117.pdf"),
    ("vic_sc_gen25_current", "Vic", "Supreme Court of Victoria SC Gen 25 (file linked from the court's page)",
     "https://www.supremecourt.vic.gov.au/sites/default/files/2026-10/"
     "SC Gen 25 Use of Artificial Intelligence by Court Users.pdf"),
    ("vic_sc_gen25_may2026", "Vic", "SC Gen 25, May 2026 upload (for comparison)",
     "https://www.supremecourt.vic.gov.au/sites/default/files/2026-05/"
     "SC Gen 25 Use of Artificial Intelligence by Court Users_0.pdf"),
    ("vic_sc_gen26", "Vic", "SC Gen 26 Practice Note for Self-Represented Litigants",
     "https://www.supremecourt.vic.gov.au/sites/default/files/2026-09/"
     "SC GEN 26 - Practice Note for Self-Represented Litigants.pdf"),
    ("qld_sc_pd5_2025_current", "Qld", "Supreme Court of Qld PD 5 of 2025 (file linked from the listing)",
     "https://www.courts.qld.gov.au/__data/assets/pdf_file/0011/889148/sc-pd-5-pf-2025.pdf"),
    ("qld_sc_pd5_2025_earlier", "Qld", "Supreme Court of Qld PD 5 of 2025, earlier file (for comparison)",
     "https://www.courts.qld.gov.au/__data/assets/pdf_file/0010/882064/sc-pd-5-pf-2025.pdf"),
    ("qld_sc_nonlawyer_guidelines", "Qld", "Supreme Court of Qld: Guidelines for Responsible Use of AI by Non-Lawyers",
     "https://www.courts.qld.gov.au/media/practice-directions/supreme-court/2027/"
     "202505accuracy-of-references-in-submissions-guidelines-for-responsible-use-of-ai-by-non-lawyers"),
    ("qld_dc_pd12_2025", "Qld", "District Court of Qld PD 12 of 2025",
     "https://www.courts.qld.gov.au/__data/assets/pdf_file/0005/889682/dcpd-12-of-2025.pdf"),
    ("qld_pe_pd7_2025", "Qld", "Planning and Environment Court of Qld PD 7 of 2025",
     "https://www.courts.qld.gov.au/__data/assets/pdf_file/0009/889659/p-and-e-cpd-07-of-2025.pdf"),
    ("wa_sc_cpd_20260925", "WA", "Supreme Court of WA Consolidated Practice Directions (as at 25 September 2026)",
     "https://www.supremecourt.wa.gov.au/_files/"
     "Consolidated Practice Directions (Original as at 25 September 2026).pdf"),
    ("wa_sc_genai_guidelines", "WA", "Supreme Court of WA Guidelines for the use of generative AI",
     "https://www.supremecourt.wa.gov.au/_files/Guidelines for the Use of Generative Artificial Intelligence.pdf"),
]
FIELDS = ["key", "jurisdiction", "description", "url", "status", "content_type", "bytes", "sha256", "local_file",
          "fetched_at_utc"]


def encode(url: str) -> str:
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, quote(p.path), p.query, p.fragment))


def main() -> None:
    out_dir = ROOT / "cache/rules"
    out_dir.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = UA
    rows = []
    for i, (key, jur, desc, url) in enumerate(SOURCES):
        if i:
            time.sleep(DELAY_S)
        try:
            r = s.get(encode(url), timeout=60)
            status, body, ctype = str(r.status_code), r.content, r.headers.get("Content-Type", "")
        except requests.RequestException as e:
            status, body, ctype = f"error:{type(e).__name__}", b"", ""
        ext = ".pdf" if body[:5] == b"%PDF-" else ".html"
        local = f"{key}{ext}" if status == "200" else ""
        if local:
            (out_dir / local).write_bytes(body)
        rows.append(dict(key=key, jurisdiction=jur, description=desc, url=url, status=status, content_type=ctype,
                         bytes=len(body), sha256=hashlib.sha256(body).hexdigest() if body else "",
                         local_file=local, fetched_at_utc=datetime.now(UTC).isoformat(timespec="seconds")))
        print(key, status, len(body), ext, flush=True)
    with (ROOT / "data/interim/rules_sources.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
