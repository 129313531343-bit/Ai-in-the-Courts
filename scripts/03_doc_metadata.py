"""Read basic facts from each cached judgment, without any AI.

For each file in data/interim/doc_manifest.csv:
- re-check its SHA-256 and that it really is a PDF or .docx (magic bytes);
- count pages and flag scanned PDFs (no usable text layer -> OCR needed);
- read the decision's own medium neutral citation from its first two pages
  (the first known-court MNC whose year matches Charlotin's decision year);
- propose court, court level and whether it is a family law matter (from the
  MNC's court code: FedCFamC1A/1F/2F are family law, FedCFamC2G is not);
- note where the copy came from, from markers in its text (a Wikisource export,
  an AustLII or NSW Caselaw print, JADE, ...). A secondary copy is never used
  as the official URL;
- check that paragraph numbering was detected and runs without gaps;
- flag disagreements with Charlotin's name/filename/label.

Output: data/interim/doc_metadata.csv. All values are proposals for review.
"""

import hashlib
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402
from aic.corpus import doc_for_row  # noqa: E402
from aic.courts import FAMILY_LAW_CODES, courts, format_mnc, own_mnc  # noqa: E402
from aic.doctext import docx_text  # noqa: E402

FIRST_PAGES = 3  # some copies have a cover page before the judgment
PROVENANCE_EDGE = 3  # header/footer lines per page searched for provenance markers
# Text markers of where a copy came from, matched case-insensitively in page
# headers and footers only (see provenance()).
PROVENANCE_MARKERS = {
    "wikisource": "Wikisource",
    "austlii": "AustLII",
    "caselaw.nsw.gov.au": "NSW Caselaw",
    "nsw caselaw": "NSW Caselaw",
    "jade.io": "JADE",
    "barnet": "BarNet",
    "fedcourt.gov.au": "Federal Court website",
    "queenslandjudgments": "Queensland Judgments",
    "sclqld.org.au": "Supreme Court Library Queensland",
    "westlaw": "Westlaw",
    "lexisnexis": "LexisNexis",
}

# Whole-line site banners accepted at the top of page 1.
PAGE1_BANNERS = {"austlii": "AustLII", "australasian legal information institute": "AustLII",
                 "nsw caselaw": "NSW Caselaw", "jade": "JADE"}


def provenance(path: Path) -> str:
    """Where a PDF copy came from, judged from running headers and footers.

    A marker counts only if it appears in the top or bottom lines of at least
    half the pages, as a printing site's URL footer does. A body line that
    happens to sit at a page edge (e.g. a bibliography entry "Law of Costs
    (LexisNexis, 5th edition, 2021)") appears on one page and is ignored.
    Two one-off signs are also accepted: a site banner that is a whole line by
    itself at the top of page 1 (AustLII's print layout without URL footers
    starts with a line reading just "AustLII"), and a Wikisource export's
    cover-page line. A footnote that cites an AustLII URL counts for nothing.
    """
    import pdfplumber

    pages_with = Counter()
    with pdfplumber.open(path) as pdf:
        n_pages = len(pdf.pages)
        first_page, banner = "", set()
        for i, pg in enumerate(pdf.pages):
            text = pg.extract_text() or ""
            if i == 0:
                first_page = text.lower()
                banner = {PAGE1_BANNERS[x.strip().lower()] for x in text.splitlines()[:PROVENANCE_EDGE]
                          if x.strip().lower() in PAGE1_BANNERS}
            lines = text.splitlines()
            edge = "\n".join(lines[:PROVENANCE_EDGE] + lines[-PROVENANCE_EDGE:]).lower()
            pages_with.update({v for k, v in PROVENANCE_MARKERS.items() if k in edge})
    found = {v for v, n in pages_with.items() if n >= max(1, n_pages / 2)} | banner
    if "exported from wikisource" in first_page:
        found.add("Wikisource")
    return ";".join(sorted(found))


def main() -> None:
    man = pd.read_csv(ROOT / "data/interim/doc_manifest.csv", dtype=str, keep_default_na=False)
    cases = pd.read_csv(ROOT / "data/interim/au_cases.csv", dtype=str, keep_default_na=False).set_index("charlotin_row")
    table = courts()
    rows = []
    for _, m in man[man.status == "200"].iterrows():
        path = ROOT / "cache/docs" / m.local_file
        data = path.read_bytes()
        kind = "pdf" if data[:5] == b"%PDF-" else "docx" if data[:2] == b"PK" and path.suffix == ".docx" else "unknown"
        c = cases.loc[m.charlotin_row]
        year = c["Date"][:4] or None
        rec = {"charlotin_row": m.charlotin_row, "file_kind": kind,
               "sha256_ok": hashlib.sha256(data).hexdigest() == m.sha256}
        if kind == "pdf":
            doc = doc_for_row(m.charlotin_row, m.local_file)
            first = "\n".join(ln.text for ln in doc.lines if ln.page <= FIRST_PAGES)
            paras = sorted(doc.markers.values())
            rec.update(n_pages=doc.n_pages, scanned=doc.scanned, n_paragraph_markers=len(paras),
                       paragraphs=f"{paras[0]}-{paras[-1]}" if paras else "",
                       paragraphs_contiguous=bool(paras) and paras == list(range(paras[0], paras[-1] + 1)))
            rec["copy_source_markers"] = provenance(path)
        elif kind == "docx":
            text = docx_text(path)
            first = text[:6000]
            rec.update(n_pages="", scanned=False, n_paragraph_markers="", paragraphs="", paragraphs_contiguous="",
                       copy_source_markers=";".join(sorted({v for k, v in PROVENANCE_MARKERS.items()
                                                            if k in text.lower()})))
        else:
            first = ""
            rec.update(n_pages="", scanned="", n_paragraph_markers="", paragraphs="", paragraphs_contiguous="",
                       copy_source_markers="")
        found, basis = own_mnc(first, year), "mnc_in_document"
        if not found and kind == "pdf":
            # Some decisions print no MNC in their own text (e.g. some VCAT orders); the
            # publisher's page-1 header (stripped from the text we analyse) may carry one.
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                found = own_mnc(pdf.pages[0].dedupe_chars().extract_text() or "", year)
            basis = "mnc_in_publisher_header"
        code = found[1] if found else ""
        rec.update(
            mnc_from_document=format_mnc(*found) if found else "",
            court_code=code or c["court_code_proposed"],
            court_code_basis=basis if found else c["court_code_basis"],
            court=table[code].name if code else (table[c["court_code_proposed"]].name
                                                 if c["court_code_proposed"] else ""),
        )
        rec["court_level"] = table[rec["court_code"]].level if rec["court_code"] else ""
        rec["family_law_proposed"] = rec["court_code"] in FAMILY_LAW_CODES
        flags = []
        if found and c["mnc_proposed"] and c["mnc_proposed"] != rec["mnc_from_document"]:
            flags.append(f"charlotin_mnc_differs:{c['mnc_proposed']}")
        if found and c["court_code_proposed"] and c["court_code_proposed"] != code:
            flags.append(f"charlotin_court_differs:{c['Court']}")
        if not found:
            flags.append("no_mnc_found_in_document")
        if rec.get("scanned"):
            flags.append("needs_ocr")
        if "Wikisource" in rec["copy_source_markers"]:
            flags.append("secondary_copy_wikisource")
        if kind == "pdf" and not rec["scanned"] and not rec["paragraphs_contiguous"]:
            flags.append("paragraph_numbering_incomplete")
        if not rec["sha256_ok"]:
            flags.append("hash_mismatch")
        rec["flags"] = ";".join(flags)
        rows.append(rec)
    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "data/interim/doc_metadata.csv", index=False)
    print(f"{len(out)} documents | kinds {out.file_kind.value_counts().to_dict()} | "
          f"hash ok {int(out.sha256_ok.sum())} | scanned {int((out.scanned == True).sum())}")  # noqa: E712
    print(f"MNC found in document: {int((out.mnc_from_document != '').sum())}")
    print(f"pages: total {pd.to_numeric(out.n_pages, errors='coerce').sum():.0f}, "
          f"max {pd.to_numeric(out.n_pages, errors='coerce').max():.0f}")
    print("court_level:", out.court_level.replace("", "(unresolved)").value_counts().to_dict())
    print("family_law_proposed:", int(out.family_law_proposed.sum()))
    print("copy_source_markers:", out.copy_source_markers.replace("", "(none)").value_counts().to_dict())
    flagged = out[out["flags"].str.contains("differs|no_mnc|needs_ocr|hash|wikisource|paragraph")]
    print(flagged[["charlotin_row", "mnc_from_document", "flags"]].to_string(index=False))


if __name__ == "__main__":
    main()
