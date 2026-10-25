"""Build data/rules.csv from the drafted cells, checking every cited paragraph.

Inputs:
  data/reference/rules_draft.csv         one row per instrument; cell text is a plain-English draft
  data/reference/rules_evidence.csv      per cell: paragraph number + a short verbatim quote
  data/reference/rules_hand_collect.csv  courts whose instruments Luc collects by hand
  cache/rules/*                          official instruments (scripts/10_fetch_rules.py)

Each quote must occur (after normalisation) in the official text, inside the
paragraph it is cited for. Paragraph spans are read from the instrument's own
numbering ("9A.", "16.", "6.7", "8.12"), accepting only numbers that move
forward, so footnote numbers and repeated running headers cannot reset them.
An instrument marked evidence_from another (the Qld District and P&E Court
directions, in identical terms to Supreme Court PD 5) is checked against its
own text using the other's quotes.

Outputs: data/rules.csv, data/interim/rules_evidence_checks.csv.
"""

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402
from aic.doctext import Line, strip_furniture  # noqa: E402
from aic.textnorm import join_lines, norm_line, norm_passage  # noqa: E402

AS_AT = "2026-10-25"
_MARK = re.compile(r"^(\d{1,2})([A-Z]?)(?:\.(\d{1,2}))?\.?\s")
COLUMNS = ["who_is_bound", "disclosure_duty", "banned_or_cautioned_uses", "verification_duty", "consequences"]
SHORT = {"who_is_bound": "who", "disclosure_duty": "disclosure", "banned_or_cautioned_uses": "uses",
         "verification_duty": "verification", "consequences": "consequences"}


def instrument_lines(source_key: str, local_file: str) -> list[Line]:
    with pdfplumber.open(ROOT / "cache/rules" / local_file) as pdf:
        pages = list(enumerate(pdf.pages, 1))
        if source_key.startswith("wa_sc_cpd"):  # only PD 9.21's own pages of the 545-page compilation
            pages = [(n, p) for n, p in pages if "PD 9.21" in (p.extract_text() or "").splitlines()[:3]]
        lines = [Line(n, norm_line(t)) for n, p in pages for t in (p.extract_text() or "").splitlines()
                 if t.strip()]
    return strip_furniture(lines, len(pages))


def paragraph_spans(lines: list[Line]) -> tuple[str, list[tuple[int, str]]]:
    """Flat text and (offset, paragraph label) for each accepted paragraph start."""
    text, starts = join_lines([ln.text for ln in lines])
    cands = [(off, m) for ln, off in zip(lines, starts, strict=True) if (m := _MARK.match(ln.text))]
    # Numbering style: decimal ("6.7", Vic) or whole numbers ("16.", NSW/Qld/WA). Numbers in the
    # other style are headings (e.g. WA's "9.21. Guidelines for the use of generative AI"), not paragraphs.
    decimal = sum(bool(m.group(3)) for _, m in cands) > len(cands) / 2
    marks, last = [], (0, "", 0)
    for off, m in cands:
        if bool(m.group(3)) != decimal:
            continue
        key = (int(m.group(1)), m.group(2), int(m.group(3) or 0))
        if key > last:
            label = m.group(1) + m.group(2) + (f".{m.group(3)}" if m.group(3) else "")
            marks.append((off, label))
            last = key
    return text, marks


def para_at(marks: list[tuple[int, str]], offset: int) -> str:
    label = ""
    for off, lab in marks:
        if off > offset:
            break
        label = lab
    return label


def main() -> None:
    sources = {r["key"]: r for r in csv.DictReader((ROOT / "data/interim/rules_sources.csv").open())}
    draft = list(csv.DictReader((ROOT / "data/reference/rules_draft.csv").open()))
    evidence = defaultdict(list)
    for e in csv.DictReader((ROOT / "data/reference/rules_evidence.csv").open()):
        evidence[e["source_key"]].append(e)

    texts = {}
    checks, out = [], []
    for d in draft:
        src = d["source_key"]
        if src not in texts:
            texts[src] = paragraph_spans(instrument_lines(src, sources[src]["local_file"]))
        text, marks = texts[src]
        refs = defaultdict(list)
        failures = 0
        for e in evidence[d["evidence_from"]]:
            q = norm_passage(e["quote"])
            found = [m.start() for m in re.finditer(re.escape(q), text)]
            paras = sorted({para_at(marks, o) for o in found})
            ok = e["paragraph"] in paras
            failures += not ok
            checks.append({"instrument_key": d["key"], "source_key": src, "column": e["column"],
                           "paragraph": e["paragraph"], "quote": e["quote"], "found": bool(found),
                           "found_in_paragraphs": ";".join(paras), "pass": ok})
            if e["paragraph"] not in refs[e["column"]]:
                refs[e["column"]].append(e["paragraph"])
        row = {"instrument": d["instrument"], "court": d["court"], "jurisdiction": d["jurisdiction"]}
        row.update({c: d[c] for c in COLUMNS})
        row["paragraph_refs"] = "; ".join(f"{SHORT[c]}: {', '.join(refs[c])}" for c in COLUMNS if refs[c])
        row.update(issued=d["issued"], commenced=d["commenced"], as_at=AS_AT, url=d["url"],
                   source_sha256=sources[src]["sha256"],
                   quotes_checked=f"{len(evidence[d['evidence_from']]) - failures}/"
                                  f"{len(evidence[d['evidence_from']])} verified in the official text",
                   checked_by="draft (Claude); not yet checked by Luc")
        out.append(row)
    for h in csv.DictReader((ROOT / "data/reference/rules_hand_collect.csv").open()):
        out.append({"instrument": "", "court": h["court"], "jurisdiction": h["jurisdiction"],
                    **{c: "pending: instrument to be collected by hand" for c in COLUMNS},
                    "paragraph_refs": "", "issued": "", "commenced": "", "as_at": AS_AT, "url": "",
                    "source_sha256": "", "quotes_checked": "", "checked_by": h["status"]})

    fields = ["instrument", "court", "jurisdiction", *COLUMNS, "paragraph_refs", "issued", "commenced", "as_at",
              "url", "source_sha256", "quotes_checked", "checked_by"]
    with (ROOT / "data/rules.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        w.writerows(out)
    with (ROOT / "data/interim/rules_evidence_checks.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, list(checks[0]))
        w.writeheader()
        w.writerows(checks)
    n_fail = sum(not c["pass"] for c in checks)
    print(f"{len(out)} rows in data/rules.csv; {len(checks)} quotes checked, {n_fail} failed")
    for c in checks:
        if not c["pass"]:
            print(f"  FAIL {c['instrument_key']} {c['column']} para {c['paragraph']} "
                  f"(found={c['found']}, in {c['found_in_paragraphs'] or '-'}): {c['quote'][:70]}")


if __name__ == "__main__":
    main()
