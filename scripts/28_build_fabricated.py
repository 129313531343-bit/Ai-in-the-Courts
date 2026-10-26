"""Evaluation items: the citations courts said were fake or wrong, as Luc checked them.

Brief (R2 "Evaluation"): "real fabricated citations: the impugned citations I verified in the
tracker, labelled with the court's characterisation". Two sources, both read by Luc:
  - the 10 spot-checked rows: impugned citations as published in the tracker (D025);
  - the 20 rows whose AI-extracted details are held back (D024): Luc checked their 47
    citations in the review page (data/review/impugned_checks.json, local; D031 E2).
His prose corrections are fixed values in aic/impugned.py, each with his note (DECISIONS.md
D034). Citations the court itself redacted ("[Redacted (Second
Case)]") cannot be checked by any tool and are left out, and counted.

Output (committed): eval/items_fabricated.csv
  id, split, kind, court_label, corpus_status, citation, source_mnc, note
kind: mnc | report | statute | other (a clause, rule or bare section with no Act named).
corpus_status: as scripts/27_build_eval.py real_label for cases; "statute" or "other" otherwise.
Split: 60/40 by tracker decision (the source document), seed 20261026.
"""

import csv
import importlib.util
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402
from aic.impugned import checked  # noqa: E402

SEED = 20261026
_spec = importlib.util.spec_from_file_location("build_eval", ROOT / "scripts/27_build_eval.py")
build_eval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_eval)
_spec = importlib.util.spec_from_file_location("review", ROOT / "scripts/13_review_server.py")
review = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(review)

ACT = re.compile(r"\b[A-Z][\w'()\- ]*\bAct\b(?:\s+\d{4})?")


def kind_of(citation: str) -> tuple[str, dict | None]:
    found = build_eval.extract(citation, ("", 0, 0))
    if found:
        return found[0]["kind"], found[0]
    return ("statute" if ACT.search(citation) else "other"), None


def main() -> None:
    t = list(csv.DictReader((ROOT / "data/interim/tracker_full.csv").open()))
    rows = []  # (tracker id, mnc, citation, label, note)
    for r in t:
        if r["verification_status"] == "luc_spot_checked" and r["impugned_citations"]:
            for part in r["impugned_citations"].split(" | "):
                m = re.match(r"^(.*) \[(\w+)\]$", part.strip())
                if m:
                    rows.append((r["id"], r["mnc"], m.group(1), m.group(2), "Luc's spot-check (D025)."))
    for case in review.impugned():
        luc = checked(case["row"])
        if luc is None:
            sys.exit(f"{case['id']} has no saved check")
        rows += [(case["id"], case["mnc"], i["citation"], i["label"], i["note"]) for i in luc]

    g = build_eval.Ground()
    ids = sorted({r[0] for r in rows})
    random.Random(SEED).shuffle(ids)
    split_of = {tid: ("dev" if i < round(0.6 * len(ids)) else "heldout") for i, tid in enumerate(ids)}
    items, redacted = [], 0
    for tid, mnc, cite, label, note in rows:
        if "redacted" in cite.lower():
            redacted += 1
            continue
        kind, parsed = kind_of(cite)
        status = build_eval.real_label(parsed, g) if parsed else kind
        items.append({"split": split_of[tid], "kind": kind, "court_label": label, "corpus_status": status,
                      "citation": cite, "source_mnc": mnc, "note": note})
    items.sort(key=lambda x: (x["split"], x["kind"], x["source_mnc"], x["citation"]))
    with (ROOT / "eval/items_fabricated.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "split", "kind", "court_label", "corpus_status", "citation", "source_mnc", "note"])
        for i, x in enumerate(items, 1):
            w.writerow([f"F{i:03d}", *x.values()])
    print(json.dumps({"citations_read": len(rows), "redacted_by_court_left_out": redacted, "items": len(items),
                      "by_split": Counter(x["split"] for x in items), "by_kind": Counter(x["kind"] for x in items),
                      "court_labels": Counter(x["court_label"] for x in items),
                      "corpus_status": Counter(x["corpus_status"] for x in items)}, indent=1))


if __name__ == "__main__":
    main()
