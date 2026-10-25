"""Draft corrections for Damien Charlotin's database (R1 step 8; Luc sends them).

Only discrepancies established deterministically or by Luc are included:
  1. court label vs the decision's own MNC (read from the judgment text);
  2. anything Luc writes in the "correction for Charlotin" box while reviewing a row.
Model-extracted values alone are never reported as corrections.

Output: data/review/charlotin_corrections.md (a draft for Luc to edit and send).
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402

# Charlotin labels that name a specific court, mapped to the MNC codes they are consistent with.
LABEL_OK = {
    "Federal Court": {"FCA", "FCAFC"}, "Federal Court of Australia": {"FCA", "FCAFC"}, "FCA": {"FCA", "FCAFC"},
    "Family Court": {"FedCFamC1A", "FedCFamC1F", "FedCFamC2F", "FamCA", "FamCAFC"},
    # QCATA is QCAT's own appeal tribunal, so "Queensland CAT" is not wrong for it.
    "Queensland CAT": {"QCAT", "QCATA"}, "Queensland Civil and Administrative Tribunal": {"QCAT", "QCATA"},
    "Supreme Court of Tasmania": {"TASSC", "TASFC", "TASCCA"},
}


def main() -> None:
    cases = pd.read_csv(ROOT / "data/interim/au_cases.csv", dtype=str, keep_default_na=False).set_index("charlotin_row")
    meta = pd.read_csv(ROOT / "data/interim/doc_metadata.csv", dtype=str, keep_default_na=False)
    items = []
    for _, m in meta.iterrows():
        c = cases.loc[m.charlotin_row]
        code = m.mnc_from_document.split()[1] if m.mnc_from_document else ""
        ok = LABEL_OK.get(c["Court"])
        if code and ok is not None and code not in ok:
            items.append((c["Case Name"], c["Date"], f"Court is listed as \"{c['Court']}\", but the decision's own "
                          f"citation is {m.mnc_from_document} ({m.court})."))
    for p in sorted((ROOT / "data/review/decisions").glob("*.json")):  # corrections Luc wrote while reviewing
        d = json.loads(p.read_text())
        if d.get("charlotin_correction", "").strip():
            c = cases.loc[p.stem]
            items.append((c["Case Name"], c["Date"], d["charlotin_correction"].strip()))

    lines = ["# Suggested corrections for the AI Hallucination Cases database (Australian entries)", "",
             "Draft for Luc to review, edit and send. Every item is checked against the decision itself.", ""]
    for name, dt, text in items:
        lines.append(f"- **{name}** ({dt}): {text}")
    if not items:
        lines.append("_No corrections yet._")
    out = ROOT / "data/review/charlotin_corrections.md"
    out.write_text("\n".join(lines) + "\n")
    print(f"{len(items)} suggested corrections -> {out}")


if __name__ == "__main__":
    main()
