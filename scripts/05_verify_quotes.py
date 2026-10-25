"""Check every Pass A quote against the judgment text and find its page and paragraph.

Pass A sends each judgment as plain text (DECISIONS D007 option b), so each
citation carries character offsets into exactly that text. A quote passes if:
  1. the cached text's SHA-256 equals the one recorded when it was sent
     (otherwise offsets would be meaningless: the whole row fails), and
  2. text[start:end] equals cited_text exactly, or (fallback, e.g. after
     whitespace differences) rapidfuzz partial_ratio >= 97 after
     normalisation, found anywhere in the judgment.
The quote's start offset gives the line, hence the PDF page and the paragraph
number (aic.doctext paragraph detection).

Output: data/interim/quote_checks.csv (one row per quote).
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402
from aic.corpus import doc_for_row  # noqa: E402
from aic.doctext import match_quote  # noqa: E402


def main() -> None:
    man = pd.read_csv(ROOT / "data/interim/doc_manifest.csv", dtype=str, keep_default_na=False)
    files = dict(zip(man.charlotin_row, man.local_file, strict=True))
    sent_path = ROOT / "data/interim/pass_a/sent_text.csv"
    sent = pd.read_csv(sent_path, dtype=str).drop_duplicates("charlotin_row", keep="last") \
        .set_index("charlotin_row") if sent_path.exists() else pd.DataFrame()
    rows = []
    for p in sorted((ROOT / "data/interim/pass_a").glob("*.json"), key=lambda x: int(x.stem)):
        rec = json.loads(p.read_text())
        if not rec.get("findings"):
            continue
        row = rec["charlotin_row"]
        doc = doc_for_row(row, files[row])
        hash_ok = row in sent.index and sent.loc[row, "text_sha256"] == doc.sha256
        for f in rec["findings"]:
            for q in f["quotes"]:
                base = {"charlotin_row": row, "quote_id": q["quote_id"], "tag": f["tag"], "finding": f["text"],
                        "cited_text": q["cited_text"]}
                if not hash_ok:
                    rows.append({**base, "method": "", "score": 0.0, "pass": False, "page": "", "paragraph": "",
                                 "location": "", "status": "hand_review",
                                 "detail": "sent-text hash mismatch or missing"})
                    continue
                start, end = q.get("start_char_index"), q.get("end_char_index")
                if start is not None and doc.text[start:end] == q["cited_text"]:
                    li = doc.line_at(start)
                    rows.append({**base, "method": "exact_offset", "score": 100.0, "pass": True,
                                 "page": doc.lines[li].page, "paragraph": doc.paragraph_at(li),
                                 "location": doc.location_at(li), "status": "pass", "detail": f"chars {start}-{end}"})
                    continue
                m = match_quote(doc, q["cited_text"])
                rows.append({**base, "method": "fuzzy", "score": m.score, "pass": m.passed, "page": m.page or "",
                             "paragraph": m.paragraph, "location": "", "status": "pass" if m.passed else "hand_review",
                             "detail": "offsets did not match exactly"})
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "data/interim/quote_checks.csv", index=False)
    if len(df):
        print(df.groupby(["status", "method"]).size().to_string())
        print(f"pass rate: {df['pass'].mean():.1%} of {len(df)} quotes; "
              f"front matter: {(df['location'] == 'front_matter').sum()}; "
              f"in unnumbered documents: {(df['location'] == 'unnumbered_document').sum()}; "
              f"other quotes without a paragraph: "
              f"{(df['pass'] & (df['paragraph'] == '') & (df['location'] == '')).sum()}")
    else:
        print("no Pass A results yet")


if __name__ == "__main__":
    main()
