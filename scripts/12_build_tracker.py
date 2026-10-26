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
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402
from aic.impugned import checked as luc_checked_impugned  # noqa: E402
from aic.verify import CHARLOTIN_PARTY  # noqa: E402

PUBLISH_EXTRACTED = {"luc_spot_checked", "auto_verified"}
# D007/D024: until AustLII answers, fields extracted by AI from an AustLII-printed copy are not
# published. Rows Luc has checked against the judgment himself are published (human-verified).
WITHHOLD_AI_FIELDS_FROM_COPIES = ("AustLII",)
WITHHELD_NOTE = "details withheld pending AustLII's reply (DECISIONS.md D007)"
# D035: in held-back rows, the impugned citations Luc read himself are published (aic/impugned.py).
CHECKED_NOTE = "; impugned citations checked by Luc against the judgment"
ANALYTICAL = ["title_as_published", "party_type", "ai_use", "ai_tool_if_stated", "error_types", "impugned_citations",
              "consequence", "regulator_referred", "practice_note_cited", "pinpoints", "charlotin_discrepancy"]
FIELDS = ["id", "mnc", "court", "court_level", "date", "title_as_published", "party_type", "ai_use",
          "ai_tool_if_stated", "error_types", "impugned_citations", "consequence", "regulator_referred",
          "practice_note_cited", "pinpoints", "official_url", "charlotin_party_type", "charlotin_outcome",
          "charlotin_error_categories", "charlotin_discrepancy", "verification_status", "details_withheld",
          "verified_on", "family_law", "source_copy", "charlotin_row"]
_CATEGORY = re.compile(r"(?:^|\|\|)\s*([A-Za-z ]+):")


def charlotin_categories(items: str) -> str:
    """Charlotin's coded error categories for a case ("Fabricated; Misrepresented"), names only."""
    return "; ".join(sorted({m.strip() for m in _CATEGORY.findall(items)}))


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
    """A field's value, with line breaks from the PDF layout collapsed ("Chat\nGPT" -> "Chat GPT")."""
    v = fields.get(name, {})
    v = v.get("value", v.get("values", ""))
    if isinstance(v, str):
        return " ".join(v.split())
    return [" ".join(x.split()) for x in v] if isinstance(v, list) else v


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
    sc_path = ROOT / "data/review/structured_corrections.json"
    structured = json.loads(sc_path.read_text()) if sc_path.exists() else {}

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
                   charlotin_error_categories=charlotin_categories(c["Hallucination Items"]),
                   date=c["Date"], verified_on=dec["reviewed_on"] if dec else "")
        if m is not None:
            rec.update(mnc=m["mnc_from_document"], court=m["court"], court_level=m["court_level"],
                       family_law=m["family_law_proposed"], source_copy=m["copy_source_markers"] or "none detected")
        else:
            rec.update(mnc=c["mnc_proposed"], court="", court_level=c["court_level_proposed"])
        pb_path = ROOT / f"data/interim/pass_b/{row}.json"
        fields = json.loads(pb_path.read_text()).get("fields", {}) if pb_path.exists() else {}
        if fields and st in PUBLISH_EXTRACTED:
            if dec:  # Luc's review wins: corrections as translated in structured_corrections.json
                fixes = structured.get(row, {})
                for name, d in dec.get("fields", {}).items():
                    if name not in fields or d.get("verdict") == "correct":
                        continue
                    fix = fixes.get(name, {})
                    applied = d.get("verdict") == "corrected" and fix.get("status") == "applied"
                    new = fix.get("value") if applied else None  # unsure or awaiting Luc: publish blank
                    if isinstance(fields[name], list):  # impugned_citations (no quote IDs: Luc read the judgment)
                        fields[name] = [dict(i, quote_ids=i.get("quote_ids", [])) for i in (new or [])]
                    else:
                        key = "values" if "values" in fields[name] else "value"
                        fields[name][key] = new if new is not None else ([] if key == "values" else "")
            rec.update(
                title_as_published=value(fields, "title_as_published"),
                party_type=value(fields, "party_type"), ai_use=value(fields, "ai_use"),
                ai_tool_if_stated=value(fields, "ai_tool_if_stated"),
                error_types="; ".join(value(fields, "error_types") or []),
                impugned_citations=" | ".join(f"{' '.join(i['citation_verbatim'].split())} [{i['characterisation']}]"
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
            if st == "auto_verified" and m is not None and any(
                    src in m["copy_source_markers"] for src in WITHHOLD_AI_FIELDS_FROM_COPIES):
                rec["details_withheld"] = WITHHELD_NOTE
                luc = luc_checked_impugned(row)
                if luc is not None:
                    rec["impugned_citations"] = " | ".join(f"{i['citation']} [{i['label']}]" for i in luc)
                    rec["details_withheld"] += CHECKED_NOTE
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
    held = public.details_withheld != ""
    luc_read = public.details_withheld.str.endswith(CHECKED_NOTE)
    public.loc[held & ~luc_read, ANALYTICAL] = ""
    public.loc[held & luc_read, [c for c in ANALYTICAL if c != "impugned_citations"]] = ""
    public.loc[srl, "title_as_published"] = ""
    public.insert(public.columns.get_loc("title_as_published") + 1, "title_withheld",
                  srl.map({True: "self-represented party (privacy)", False: ""}))
    public.to_csv(ROOT / "data/tracker.csv", index=False)

    published = df[df.verification_status.isin(PUBLISH_EXTRACTED) & (df.details_withheld == "")]
    coded = df[df.charlotin_error_categories != ""]
    misrep = coded[coded.charlotin_error_categories.str.contains("Misrepresented|False Quotes")]
    ours = published[published.error_types != ""]
    ours_mis = ours[ours.error_types.str.contains("misdescribed_authority|false_quote")]
    stats = {
        "cases_in_tracker": len(df),
        "by_verification_status": df.verification_status.value_counts().to_dict(),
        "rows_publishing_extracted_fields": len(published),
        "rows_with_details_withheld_pending_austlii": int((df.details_withheld != "").sum()),
        # Used by the checklist: Charlotin's own coding of all Australian rows (independent of our extraction).
        "share_misrepresentation_or_false_quote": {
            "numerator": len(misrep), "denominator": len(coded),
            "percent": round(100 * len(misrep) / len(coded), 1) if len(coded) else None,
            "source": "Charlotin's coding",
            "definition": "Australian rows whose Charlotin error categories include 'Misrepresented' or "
                          "'False Quotes', over Australian rows with any coded category"},
        "share_from_published_extraction": {
            "numerator": len(ours_mis), "denominator": len(ours),
            "definition": "published rows whose extracted error types include misdescribed_authority or false_quote"},
    }
    (ROOT / "data/stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
