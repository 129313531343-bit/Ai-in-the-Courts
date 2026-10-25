"""Verify every proposed tracker row automatically and list the rows that need Luc.

For each row with Pass B output, runs aic.verify.check_row against the cached
judgment text and the verified quotes. Writes:
  data/interim/verification_checks.csv  one line per check (row, check, passed, detail)
  data/interim/row_status.csv           verification_status per row:
      auto_verified        every automatic check passed (not human-reviewed)
      flagged_for_review   at least one check failed
      not_auto_verifiable  no usable text or no extraction (scanned, manual-only source, refusal, ...)
      no_public_source     no free judgment text to verify against
  data/review/luc_queue.csv             what Luc reviews: the pre-registered random 10, plus every
                                        flagged and not_auto_verifiable row
  data/interim/agreement.json           agreement with Charlotin (percentage and Cohen's kappa)
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402
from aic.corpus import doc_for_row  # noqa: E402
from aic.verify import CHARLOTIN_PARTY, check_row, cohen_kappa  # noqa: E402


def main() -> None:
    cases = pd.read_csv(ROOT / "data/interim/au_cases.csv", dtype=str, keep_default_na=False)
    meta = pd.read_csv(ROOT / "data/interim/doc_metadata.csv", dtype=str, keep_default_na=False) \
        .set_index("charlotin_row")
    man = pd.read_csv(ROOT / "data/interim/doc_manifest.csv", dtype=str, keep_default_na=False)
    files = dict(zip(man.charlotin_row, man.local_file, strict=True))
    qpath = ROOT / "data/interim/quote_checks.csv"
    qc = pd.read_csv(qpath, dtype=str, keep_default_na=False) if qpath.exists() else pd.DataFrame(
        columns=["charlotin_row", "quote_id", "pass", "paragraph", "cited_text"])
    qc["pass"] = qc["pass"] == "True"
    spot = set(pd.read_csv(ROOT / "data/review/spot_check_sample.csv", dtype=str).charlotin_row)

    checks, status = [], []
    for _, c in cases.iterrows():
        row = c.charlotin_row
        pb_path = ROOT / f"data/interim/pass_b/{row}.json"
        pb = json.loads(pb_path.read_text()) if pb_path.exists() else {}
        if c.no_public_source == "True":
            st, why = "no_public_source", c.source_kind
        elif row not in files:
            st, why = "not_auto_verifiable", f"no cached judgment ({c.source_kind}): read by hand"
        elif meta.loc[row, "scanned"] == "True":
            st, why = "not_auto_verifiable", "scanned PDF: needs OCR or reading by hand"
        elif not pb.get("fields"):
            st, why = "not_auto_verifiable", pb.get("needs_hand_review") or pb.get("error") or "no Pass B output yet"
        else:
            # to_dict, not itertuples: itertuples silently renames the "pass" column (a Python keyword).
            quotes = {r["quote_id"]: r for r in qc[qc.charlotin_row == row].to_dict("records")}
            res = check_row(pb["fields"], quotes, doc_for_row(row, files[row]), meta.loc[row].to_dict(),
                            c.to_dict(), pb.get("dropped_unsupported", []))
            checks += [{"charlotin_row": row, "check": n, "passed": ok, "detail": d} for n, ok, d in res]
            failed = [n for n, ok, _ in res if not ok]
            st, why = ("flagged_for_review", ";".join(sorted(set(failed)))) if failed else ("auto_verified", "")
        status.append({"charlotin_row": row, "verification_status": st, "reason": why,
                       "in_random_spot_check": row in spot})

    st = pd.DataFrame(status)
    st.to_csv(ROOT / "data/interim/row_status.csv", index=False)
    pd.DataFrame(checks, columns=["charlotin_row", "check", "passed", "detail"]).to_csv(
        ROOT / "data/interim/verification_checks.csv", index=False)
    needs_luc = st.verification_status.isin(["flagged_for_review", "not_auto_verifiable"])
    queue = st[st.in_random_spot_check | needs_luc].copy()

    # Order Luc's queue by purpose and effort. Minutes are planning estimates, not measurements.
    def tier(r) -> tuple[int, str, int]:
        if r.in_random_spot_check:
            return 1, "random spot-check: check every field", 12
        if r.verification_status == "flagged_for_review" and r.reason == "characterisation_has_textual_cue":
            return 3, "quick: confirm the flagged characterisation(s) only", 3
        if r.verification_status == "flagged_for_review":
            return 2, "flagged: check the flagged fields", 8
        return 4, "read the judgment by hand (no automatic checks possible)", 15
    queue[["priority", "task", "est_minutes"]] = queue.apply(lambda r: pd.Series(tier(r)), axis=1)
    queue = queue.sort_values(["priority", "charlotin_row"], key=lambda c: c.astype(int))
    queue.to_csv(ROOT / "data/review/luc_queue.csv", index=False)

    # Agreement with Charlotin on party type, over rows with an extracted party type.
    a, b = [], []
    for _, c in cases.iterrows():
        pb_path = ROOT / f"data/interim/pass_b/{c.charlotin_row}.json"
        if pb_path.exists() and c["Party(ies)"] in CHARLOTIN_PARTY:
            v = json.loads(pb_path.read_text()).get("fields", {}).get("party_type", {}).get("value")
            if v:
                a.append(v)
                b.append(CHARLOTIN_PARTY[c["Party(ies)"]])
    k = cohen_kappa(a, b)
    agreement = {"party_type": {"n": len(a), "percent_agree": round(100 * sum(x == y for x, y in zip(a, b,
                 strict=True)) / len(a), 1) if a else None, "cohen_kappa": round(k, 3) if k is not None else None,
                 "raters": "Pass B extraction vs Charlotin (Luc's spot-check agreement is computed after review)"}}
    (ROOT / "data/interim/agreement.json").write_text(json.dumps(agreement, indent=2) + "\n")

    print(st.verification_status.value_counts().to_string())
    print(f"Luc's queue: {len(queue)} rows, about {queue.est_minutes.sum() / 60:.1f} h")
    print(queue.groupby(["priority", "task"]).agg(rows=("charlotin_row", "size"),
                                                  minutes=("est_minutes", "sum")).to_string())
    print("agreement:", json.dumps(agreement))


if __name__ == "__main__":
    main()
