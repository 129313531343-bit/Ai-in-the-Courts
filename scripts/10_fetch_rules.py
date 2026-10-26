"""Fetch the official AI practice notes and directions used in rules.csv.

Only court and government sites, each checked first for robots.txt rules (none
disallow these files or set AI content signals; checked 25 Oct 2026). One
request every 5 s. Files go to cache/rules/ (not committed); the manifest with
URLs, dates and SHA-256 hashes, data/interim/rules_sources.csv, is committed.

Two instruments are saved by Luc in his own browser, because the site refuses
automated requests (checked 26 Oct 2026): the Federal Court (HTTP 403, even for
robots.txt) and the Fair Work Commission (HTTP 403). He puts them in rules_inbox/
(not committed); --inbox copies them to cache/rules/ and records their hashes.
Everything else below is fetched here.

Usage: python scripts/10_fetch_rules.py [--only key1,key2 | --inbox]   (default: fetch all)

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
    # Added 26 Oct 2026 (previously on Luc's hand-collection list; these sites allow it).
    ("fcfcoa_pd_ai", "Cth", "FCFCOA Practice Direction: Use of Artificial Intelligence (PD-AI)",
     "https://www.fcfcoa.gov.au/sites/default/files/2026-05/"
     "fcfcoa_pd_-_use_of_artificial_intelligence_-_pd-ai_-_0526v1.pdf"),
    ("art_genai_pd", "Cth", "Administrative Review Tribunal (Generative AI) Practice Direction",
     "https://www.art.gov.au/sites/default/files/2026-08/"
     "Administrative Review Tribunal (Generative AI) Practice Direction.pdf"),
    ("vcat_pnvcat11", "Vic", "VCAT Practice Note PNVCAT11: Use of generative artificial intelligence",
     "https://www.vcat.vic.gov.au/media/551/download"),
    ("qcat_pd10_2025", "Qld", "QCAT Practice Direction No 10 of 2025: Accuracy of References in Submissions",
     "https://www.qcat.qld.gov.au/__data/assets/pdf_file/0006/884940/"
     "qcat-practice-direction-10-of-2025-accuracy-of-references-in-submissions.pdf"),
    ("wadc_pd_general", "WA", "District Court of WA Practice Directions (General)",
     "https://www.districtcourt.wa.gov.au/_files/Practice_Directions_General.pdf"),
    ("wadc_pd_civil", "WA", "District Court of WA Practice Directions (Civil)",
     "https://www.districtcourt.wa.gov.au/_files/Practice_Directions_Civil.pdf"),
    ("wadc_pn_general", "WA", "District Court of WA Practice Notes (General)",
     "https://www.districtcourt.wa.gov.au/_files/PN GENERAL - with annexures.pdf"),
    ("sat_practice_notes", "WA", "State Administrative Tribunal (WA): practice notes page",
     "https://www.sat.justice.wa.gov.au/P/practice_notes.aspx"),
    # The County Court's page is built with JavaScript, so this link was read off it in a browser
    # (robots.txt allows access); the file itself is fetched here.
    ("vcc_ai_pn", "Vic", "County Court of Victoria: Use of Artificial Intelligence by Court Users Practice Note",
     "https://www.countycourt.vic.gov.au/files/documents/2026-06/use-artificial-intelligence-court-users-practice-note.docx"),
]
INBOX = [  # (key, jurisdiction, description, url, file Luc saved in rules_inbox/)
    ("fca_gpn_ai", "Cth", "Federal Court of Australia: Use of Generative AI Practice Note (GPN-AI), "
     "the Court's web page printed to PDF by Luc",
     "https://www.fedcourt.gov.au/law-and-practice/practice-documents/practice-notes/gpn-ai", "fca.pdf"),
    ("fwc_genai_gn", "Cth", "Fair Work Commission: Guidance note, Use of generative artificial intelligence in "
     "Commission cases (published 24 Aug 2026, commenced 20 Oct 2026)",
     "https://www.fwc.gov.au/documents/resources/guidance-note-use-of-generative-ai-in-commission-cases.pdf",
     "fwc.pdf"),
]
FIELDS = ["key", "jurisdiction", "description", "url", "status", "content_type", "bytes", "sha256", "local_file",
          "fetched_at_utc"]


def encode(url: str) -> str:
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, quote(p.path), p.query, p.fragment))


def import_inbox(out_dir: Path) -> list[dict]:
    """Manifest rows for the files Luc saved in rules_inbox/, copied to cache/rules/."""
    rows = []
    for key, jur, desc, url, name in INBOX:
        src = ROOT / "rules_inbox" / name
        if not src.exists():
            print(key, "not in rules_inbox yet", flush=True)
            continue
        body = src.read_bytes()
        local = f"{key}{src.suffix}"
        (out_dir / local).write_bytes(body)
        saved = datetime.fromtimestamp(src.stat().st_mtime, UTC).isoformat(timespec="seconds")
        rows.append(dict(key=key, jurisdiction=jur, description=desc, url=url, status="saved by Luc in his browser",
                         content_type="application/pdf" if body[:5] == b"%PDF-" else "", bytes=len(body),
                         sha256=hashlib.sha256(body).hexdigest(), local_file=local, fetched_at_utc=saved))
        print(key, "copied from rules_inbox", len(body), flush=True)
    return rows


def main() -> None:
    out_dir = ROOT / "cache/rules"
    out_dir.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = UA
    inbox = "--inbox" in sys.argv
    only = {x[0] for x in INBOX} if inbox else \
        set(sys.argv[sys.argv.index("--only") + 1].split(",")) if "--only" in sys.argv else None
    manifest = ROOT / "data/interim/rules_sources.csv"
    kept = [r for r in csv.DictReader(manifest.open())] if (only and manifest.exists()) else []
    kept = [r for r in kept if r["key"] not in only] if only else []
    rows = import_inbox(out_dir) if inbox else []
    for i, (key, jur, desc, url) in enumerate([x for x in SOURCES if not only or x[0] in only]):
        if i:
            time.sleep(DELAY_S)
        try:
            r = s.get(encode(url), timeout=60)
            status, body, ctype = str(r.status_code), r.content, r.headers.get("Content-Type", "")
        except requests.RequestException as e:
            status, body, ctype = f"error:{type(e).__name__}", b"", ""
        ext = ".pdf" if body[:5] == b"%PDF-" else ".docx" if body[:2] == b"PK" else ".html"
        local = f"{key}{ext}" if status == "200" else ""
        if local:
            (out_dir / local).write_bytes(body)
        rows.append(dict(key=key, jurisdiction=jur, description=desc, url=url, status=status, content_type=ctype,
                         bytes=len(body), sha256=hashlib.sha256(body).hexdigest() if body else "",
                         local_file=local, fetched_at_utc=datetime.now(UTC).isoformat(timespec="seconds")))
        print(key, status, len(body), ext, flush=True)
    order = [x[0] for x in SOURCES + INBOX]
    rows = sorted(kept + rows, key=lambda r: order.index(r["key"]) if r["key"] in order else len(order))
    with manifest.open("w", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
