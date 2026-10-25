"""Build data/tracker.csv (public), data/interim/tracker_full.csv (local) and data/stats.json.

One row per Australian case in Charlotin's database. Columns follow the brief,
plus `ai_use` (D013), the copy's provenance and the review trail.

What a row publishes depends on its verification_status (D014, D016):
  luc_spot_checked     extracted fields, with Luc's corrections applied
  auto_verified        extracted fields (every automatic check passed)
  flagged_for_review   document facts and Charlotin's coding only, until Luc resolves the flags
  not_auto_verifiable  document facts and Charlotin's coding only
  no_public_source     Charlotin's coding only
Document facts = MNC, court, level and date, read deterministically from the
judgment (scripts/03_doc_metadata.py).

Luc's review decisions live in data/review/decisions/<charlotin_row>.json
(written by the review page): {"reviewed_on": "YYYY-MM-DD", "fields": {field:
{"verdict": "correct"|"corrected"|"unsure", "value": ...}}, "note": "..."}.

IDs (AIC-0001, ...) are assigned once in data/reference/id_map.csv and never reused.
"""

import csv
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402
from aic.verify import CHARLOTIN_PARTY  # noqa: E402

PUBLISH_EXTRACTED = {"luc_spot_checked", "auto_verified"}
FIELDS = ["id", "mnc", "court", "court_level", "date", "title_as_published", "party_type", "ai_use",
          "ai_tool_if_stated", "error_types", "impugned_citations", "consequence", "regulator_referred",
          "practice_note_cited", "pinpoints", "official_url", "charlotin_party_type", "charlotin_outcome",
          "charlotin_discrepancy", "verification_status", "verified_on", "family_law", "source_copy",
          "charlotin_row"]


def stable_ids(rows: list[str], dates: dict[str, str]) -> dict[str, str]:
    path = ROOT / "data/reference/id_map.csv"
    ids = dict(csv.reader(path.open())) if path.exists() else {}
    ids.pop("charlotin_row", None)
    n = max((int(v.split("-")[1]) for v in ids.values()), default=0)
    for r in sorted((r for r in rows if r not in ids), key=lambda r: (dates[r], int(r))):
        n += 1
        ids[r] = f"AIC-{n:04d}"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["charlotin_row", "id"])
        w.writerows(sorted(ids.items(), key=lambda kv: kv[1]))
    return ids


def value(fields: dict, name: str):
    v = fields.get(name, {})
    return v.get("value", v.get("values", ""))


def main() -> None:
    cases = pd.read_csv(ROOT / "data/interim/au_cases.csv", dtype=str, keep_default_na=False)
    meta = pd.read_csv(ROOT / "data/interim/doc_metadata.csv", dtype=str, keep_default_na=False) \
        .set_index("charlotin_row")
    status = pd.read_csv(ROOT / "data/interim/row_status.csv", dtype=str, keep_default_na=False) \
        .set_index("charlotin_row")
    qc_path = ROOT / "data/interim/quote_checks.csv"
    qc = pd.read_csv(qc_path, dtype=str, keep_default_na=False) if qc_path.exists() else pd.DataFrame(
        columns=["charlotin_row", "quote_id", "paragraph"])
    ids = stable_ids(list(cases.charlotin_row), dict(zip(cases.charlotin_row, cases.Date, strict=True)))

    out = []
    for _, c in cases.iterrows():
        row = c.charlotin_row
        m = meta.loc[row] if row in meta.index else None
        st = status.loc[row, "verification_status"] if row in status.index else "not_auto_verifiable"
        dec_path = ROOT / f"data/review/decisions/{row}.json"
        dec = json.loads(dec_path.read_text()) if dec_path.exists() else None
        if dec:
            st = "luc_spot_checked"
        rec = {k: "" for k in FIELDS}
        rec.update(id=ids[row], charlotin_row=row, verification_status=st,
                   charlotin_party_type=c["Party(ies)"], charlotin_outcome=c["Outcome"],
                   date=c["Date"], verified_on=dec["reviewed_on"] if dec else "")
        if m is not None:
            rec.update(mnc=m["mnc_from_document"], court=m["court"], court_level=m["court_level"],
                       family_law=m["family_law_proposed"], source_copy=m["copy_source_markers"] or "none detected")
        else:
            rec.update(mnc=c["mnc_proposed"], court="", court_level=c["court_level_proposed"])
        pb_path = ROOT / f"data/interim/pass_b/{row}.json"
        fields = json.loads(pb_path.read_text()).get("fields", {}) if pb_path.exists() else {}
        if fields and st in PUBLISH_EXTRACTED:
            if dec:  # Luc's corrections win
                for name, d in dec.get("fields", {}).items():
                    if d.get("verdict") == "corrected" and name in fields:
                        key = "values" if "values" in fields[name] else "value"
                        if isinstance(fields[name], dict):
                            fields[name][key] = d.get("value")
            rec.update(
                title_as_published=value(fields, "title_as_published"),
                party_type=value(fields, "party_type"), ai_use=value(fields, "ai_use"),
                ai_tool_if_stated=value(fields, "ai_tool_if_stated"),
                error_types="; ".join(value(fields, "error_types") or []),
                impugned_citations=" | ".join(f"{i['citation_verbatim']} [{i['characterisation']}]"
                                              for i in fields.get("impugned_citations", [])),
                consequence="; ".join(value(fields, "consequence") or []),
                regulator_referred=value(fields, "regulator_referred"),
                practice_note_cited=value(fields, "practice_note_cited"),
            )
            q = {r["quote_id"]: (r["paragraph"] or ("orders" if r.get("location") == "front_matter" else ""))
                 for r in qc[qc.charlotin_row == row].to_dict("records")}
            used = {qid for k, v in fields.items() if k in ("error_types", "consequence", "regulator_referred",
                                                            "ai_use", "practice_note_cited")
                    for qid in v.get("quote_ids", [])} | {qid for i in fields.get("impugned_citations", [])
                                                          for qid in i["quote_ids"]}
            paras = sorted({q[x] for x in used if q.get(x)}, key=lambda p: int(p) if p.isdigit() else 0)
            rec["pinpoints"] = ", ".join(p if p == "orders" else f"[{p}]" for p in paras)
            ch = CHARLOTIN_PARTY.get(c["Party(ies)"], "")
            if ch and rec["party_type"] and ch != rec["party_type"]:
                rec["charlotin_discrepancy"] = (f"party type: Charlotin {c['Party(ies)']!r}, "
                                                f"judgment {rec['party_type']!r}")
        out.append(rec)

    df = pd.DataFrame(out, columns=FIELDS).sort_values("id")
    df.to_csv(ROOT / "data/interim/tracker_full.csv", index=False)  # local only (gitignored)
    # Public version (PRIVACY.md decisions B1 and C1): no case titles for rows involving a
    # self-represented party, judged protectively from either our extraction or Charlotin's coding.
    srl = (df.party_type == "self_represented") | (df.charlotin_party_type == "Pro Se Litigant")
    public = df.copy()
    public.loc[srl, "title_as_published"] = ""
    public.insert(public.columns.get_loc("title_as_published") + 1, "title_withheld",
                  srl.map({True: "self-represented party (privacy)", False: ""}))
    public.to_csv(ROOT / "data/tracker.csv", index=False)

    pub = df[df.verification_status.isin(PUBLISH_EXTRACTED)]
    with_errors = pub[pub.error_types != ""]
    misrep = with_errors[with_errors.error_types.str.contains("misdescribed_authority|false_quote")]
    stats = {
        "cases_in_tracker": len(df),
        "by_verification_status": df.verification_status.value_counts().to_dict(),
        "rows_publishing_extracted_fields": len(pub),
        "share_misrepresentation_or_false_quote": {
            "numerator": len(misrep), "denominator": len(with_errors),
            "percent": round(100 * len(misrep) / len(with_errors), 1) if len(with_errors) else None,
            "definition": "rows publishing extracted fields whose error types include misdescribed_authority "
                          "or false_quote, over rows publishing extracted fields with any error type"},
    }
    (ROOT / "data/stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
