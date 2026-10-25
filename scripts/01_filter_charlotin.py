"""Filter Charlotin's AI Hallucination Cases CSV to Australian rows.

Inputs : raw/charlotin_download_<date>.csv  (unchanged download, CC BY 4.0)
Outputs: raw/charlotin_au_<date>.csv         (Australian rows, Charlotin's text unchanged)
         data/interim/au_cases.csv          (same rows plus our columns; Charlotin's columns kept)
         data/interim/au_summary.json       (every count quoted in the docs comes from here)

Our court columns here are first proposals from Charlotin's name, filename or
court label. scripts/03_doc_metadata.py then reads each judgment's own MNC,
which takes precedence, and the reviewer confirms it.
"""

import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402
from aic.courts import courts, find_mnc, format_mnc  # noqa: E402

DOC_BASE = "https://www.damiencharlotin.com"
# AustLII case URLs encode the MNC: /au/cases/<jurisdiction>/<CODE>/<year>/<number>.html.
# Read from the URL text only; AustLII itself is never fetched.
AUSTLII_CASE_RE = re.compile(r"/au/cases/[a-z]+/([A-Za-z0-9]+)/((?:19|20)\d\d)/(\d+)\.html")

# Used only when no MNC is visible. Only labels that name one court are
# mapped. Charlotin's labels are not always right (e.g. "Federal Court" on a
# FedCFamC2G decision), so an MNC always wins over this table.
COURT_LABEL_TO_CODE = {
    "Fair Work Commission": "FWC",
    "Federal Court": "FCA", "Federal Court of Australia": "FCA", "FCA": "FCA",
    "Administrative Review Tribunal": "ARTA", "Administrative Review Tribunal of Australia": "ARTA",
    "ARTA": "ARTA", "ART Australia": "ARTA",
    "Queensland IRC": "QIRC",
    "Victorian CAT": "VCAT", "Victoria CAT": "VCAT",
    "Queensland CAT": "QCAT", "Queensland Civil and Administrative Tribunal": "QCAT",
    "NSW SC": "NSWSC", "SC New South Wales": "NSWSC", "Supreme Court (NSW)": "NSWSC",
    "NSW CA": "NSWCA",
    "NSW D.C.": "NSWDC", "District Court of New South Wales": "NSWDC", "D. New South Wales": "NSWDC",
    "NSW LEC": "NSWLEC",
    "IRC New South Wales": "NSWIRComm", "NSW IRComm": "NSWIRComm",
    "NSW Industrial Relations Commission": "NSWIRComm", "Industrial Relations Commission (NSW)": "NSWIRComm",
    "Supreme Court of Tasmania": "TASSC", "TASSC": "TASSC",
    "County Court of Victoria": "VCC", "Melbourne County Court": "VCC", "VCC": "VCC",
    "SC Victoria": "VSC", "Victoria SC": "VSC", "Supreme Court of Victoria": "VSC",
    "Victoria SCA": "VSCA", "Victoria CA": "VSCA", "CA Victoria": "VSCA", "SC Victoria (CA)": "VSCA",
    "Queensland BCCMC": "QBCCMCmr", "Queensland's BCCMC": "QBCCMCmr",
    "Supreme Court of Queensland": "QSC",
    "Queensland ICmr": "QICmr",
    "Victoria BAB": "VBAB",
    "ACT SC": "ACTSC",
    "ACT CAT": "ACAT",
    "Trade Marks Office": "ATMO",
    "THE COURT OF APPEAL (WA)": "WASCA", "Supreme Court of Western Australia - Court of Appeal": "WASCA",
    "NSW Personal Injury Commission": "NSWPIC",
    # Deliberately unmapped (ambiguous): "NSW", "NSW CAT" (division unknown),
    # "Queensland", "South Australia", "Family Court", "Federal Circuit and
    # Family Court" (division unknown), "FedCFam", "".
}


def classify_source(src: str) -> str:
    s = src.strip()
    if not s:
        return "none"
    if s.startswith("/documents/"):
        return "charlotin_document"
    if "caselaw.nsw.gov.au" in s:
        return "official_nsw_caselaw"  # NSW Caselaw terms exclude robots: read by hand
    if "austlii.edu.au" in s:
        return "austlii_manual_only"  # AustLII blocks bots and reserves AI uses: read by hand
    if "thomsonreuters.com" in s or "westlaw" in s.lower():
        return "paywalled_westlaw"
    return "secondary_media_or_blog"


def main(download: Path) -> None:
    date = download.stem.rsplit("_", 1)[-1]
    df = pd.read_csv(download, dtype=str, keep_default_na=False)
    au = df[df["State(s)"].str.strip() == "Australia"].copy()
    au.to_csv(ROOT / f"raw/charlotin_au_{date}.csv", index=False)

    table = courts()
    out = au.copy()
    out.insert(0, "charlotin_row", au.index.astype(int))
    mnc, code, basis = [], [], []
    for _, r in au.iterrows():
        m = find_mnc(r["Case Name"]) or find_mnc(r["Source"])
        a = AUSTLII_CASE_RE.search(r["Source"])
        if not m and a and a.group(1) in table:
            m = (a.group(2), a.group(1), a.group(3))
        if m:
            mnc.append(format_mnc(*m))
            code.append(m[1])
            basis.append("mnc_in_charlotin_name_filename_or_url")
        elif COURT_LABEL_TO_CODE.get(r["Court"]):
            mnc.append("")
            code.append(COURT_LABEL_TO_CODE[r["Court"]])
            basis.append("charlotin_court_label")
        else:
            mnc.append("")
            code.append("")
            basis.append("unresolved")
    out["mnc_proposed"] = mnc
    out["court_code_proposed"] = code
    out["court_code_basis"] = basis
    out["court_level_proposed"] = [table[c].level if c else "" for c in code]
    out["source_kind"] = au["Source"].map(classify_source)
    out["source_url"] = [DOC_BASE + s if s.startswith("/documents/") else s for s in au["Source"]]
    # "No public source" = no free text of the judgment that a person can read.
    # AustLII and NSW Caselaw links count as public (a person can open them).
    out["no_public_source"] = out["source_kind"].isin(["none", "paywalled_westlaw", "secondary_media_or_blog"])
    out.to_csv(ROOT / "data/interim/au_cases.csv", index=False)

    summary = {
        "download_file": download.name,
        "rows_in_download": len(df),
        "australian_rows": len(au),
        "party_type_charlotin": au["Party(ies)"].replace("", "(blank)").value_counts().to_dict(),
        "source_kind": out["source_kind"].value_counts().to_dict(),
        "court_code_basis": out["court_code_basis"].value_counts().to_dict(),
        "court_level_proposed": out["court_level_proposed"].replace("", "(unresolved)").value_counts().to_dict(),
        "decision_dates": [au["Date"].min(), au["Date"].max()],
    }
    (ROOT / "data/interim/au_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "raw/charlotin_download_2026-10-25.csv")
