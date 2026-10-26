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
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd
import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402
from aic.doctext import Line, strip_furniture  # noqa: E402
from aic.docxnum import numbered_lines  # noqa: E402
from aic.textnorm import join_lines, norm_line, norm_passage  # noqa: E402

AS_AT = "2026-10-25"
_MARK = re.compile(r"^(\d{1,2})([A-Z]?)(?:\.(\d{1,2}))?\.?\s")
COLUMNS = ["who_is_bound", "disclosure_duty", "banned_or_cautioned_uses", "verification_duty", "consequences"]
SHORT = {"who_is_bound": "who", "disclosure_duty": "disclosure", "banned_or_cautioned_uses": "uses",
         "verification_duty": "verification", "consequences": "consequences"}


def instrument_lines(source_key: str, local_file: str) -> list[Line]:
    if local_file.endswith(".docx"):  # Word: restore automatic paragraph numbers (aic.docxnum)
        return [Line(1, norm_line(t)) for t in numbered_lines(ROOT / "cache/rules" / local_file) if t.strip()]
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
    marks, last = [], None
    for off, m in cands:
        if bool(m.group(3)) != decimal:
            continue
        key = (int(m.group(1)), m.group(2), int(m.group(3) or 0))
        if last is None or plausible_next(last, key, decimal):
            label = m.group(1) + m.group(2) + (f".{m.group(3)}" if m.group(3) else "")
            marks.append((off, label))
            last = key
    return text, marks


def plausible_next(last: tuple[int, str, int], key: tuple[int, str, int], decimal: bool) -> bool:
    """Could `key` be the paragraph after `last`? Only small steps count, so a wrapped line that happens
    to start with a number ("41 and 57 of the Barristers' Conduct Rules") or a footnote is not a paragraph.
    Whole numbers: 13 -> 14 (or 15, one skipped), 9 -> 9A -> 9B -> 10. Decimal: 4.20 -> 4.21, 4.21 -> 5.1."""
    (ln, ll, lm), (n, lt, m) = last, key
    if decimal:
        return (n == ln and lm < m <= lm + 2) or (n == ln + 1 and m in (0, 1))
    return (n == ln and lt > ll) or (ln < n <= ln + 2)


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

    dec_path = ROOT / "data/review/rules_decisions.json"
    decisions = json.loads(dec_path.read_text()) if dec_path.exists() else {}
    holds_path = ROOT / "data/review/rules_holds.json"  # corrections held back pending Luc's confirmation
    holds = json.loads(holds_path.read_text()) if holds_path.exists() else {}
    ov_path = ROOT / "data/review/rules_overrides.json"  # final text where Luc's note mixed instruction and wording
    overrides = json.loads(ov_path.read_text()) if ov_path.exists() else {}
    by_source = {d["source_key"]: d["key"] for d in draft}

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
        # Luc's check (review page, Rules tab). Instruments in identical terms are covered by the
        # check of the instrument they reuse.
        own = decisions.get(d["key"])
        dec = own or decisions.get(by_source.get(d["evidence_from"], ""))
        checked_by = "draft (Claude); not yet checked by Luc"
        if dec:
            verdicts = {c: dec["cells"].get(c, {}).get("verdict") for c in COLUMNS}
            all_held = holds.get(d["key"]) or holds.get(by_source.get(d["evidence_from"], ""), {})
            # A hold resolved as "keep_draft" means Luc confirmed the draft wording: treat it as checked.
            held = {c: h for c, h in all_held.items()
                    if not (isinstance(h, dict) and h.get("resolution") == "keep_draft")}
            for c in all_held:
                verdicts[c] = "held" if c in held else "correct"
            if own:
                for c in COLUMNS:
                    v = dec["cells"].get(c, {})
                    final = overrides.get(d["key"], {}).get(c, {}).get("text")  # set from Luc's instructions
                    if c in held:
                        continue
                    if final:
                        row[c] = final
                    elif v.get("verdict") == "corrected" and v.get("value"):
                        row[c] = v["value"]
            unsure = [c + (" (held: awaiting Luc)" if v == "held" else "")
                      for c, v in verdicts.items() if v != "correct" and v != "corrected"]
            via = "" if own else " (via the identical Supreme Court direction)"
            checked_by = (f"checked by Luc on {dec['reviewed_on']}{via}" if not unsure
                          else f"partly checked by Luc on {dec['reviewed_on']}{via}; unsure: {', '.join(unsure)}")
        row["paragraph_refs"] = "; ".join(f"{SHORT[c]}: {', '.join(refs[c])}" for c in COLUMNS if refs[c])
        row.update(issued=d["issued"], commenced=d["commenced"], as_at=AS_AT, url=d["url"],
                   source_sha256=sources[src]["sha256"],
                   quotes_checked=f"{len(evidence[d['evidence_from']]) - failures}/"
                                  f"{len(evidence[d['evidence_from']])} verified in the official text",
                   checked_by=checked_by)
        out.append(row)
    none_path = ROOT / "data/reference/rules_none.csv"  # courts searched with no AI guidance found (brief's wording)
    for n in (csv.DictReader(none_path.open()) if none_path.exists() else []):
        when = pd.Timestamp(n["checked_on"]).strftime("%-d %B %Y")
        out.append({"instrument": "No specific AI guidance found", "court": n["court"],
                    "jurisdiction": n["jurisdiction"],
                    **{c: f"No specific guidance found as at {when}." for c in COLUMNS},
                    "paragraph_refs": "", "issued": "", "commenced": "", "as_at": n["checked_on"], "url": n["url"],
                    "source_sha256": ";".join(sources[k]["sha256"][:12] for k in n["source_keys"].split(";")),
                    "quotes_checked": f"searched: {n['documents_searched']}",
                    "checked_by": "searched by script; not yet confirmed by Luc"})
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
