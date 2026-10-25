"""Pass A: quote extraction with Citations, via the Message Batches API.

Each judgment goes to the API as a plain-text document: the text extracted
locally by aic.doctext, with page furniture removed (running headers and
footers, page numbers, AustLII's banner, header block and URL footers,
Wikisource cover pages). This is DECISIONS D007 option (b). Claude writes one
tagged line per finding, backed by citations. A plain-text citation gives
character offsets into exactly the text we sent, so 05_verify_quotes.py can
check each quote byte-for-byte and map it to a page and paragraph number.

The sent text's SHA-256 is recorded per row in data/interim/pass_a/sent_text.csv.

Pass A only gathers quotes. It proposes no tracker values; Pass B does that.

Usage:
  python scripts/04_pass_a.py estimate [--dev|--rows 1,2,3] [--model sonnet|opus]   # no spend
  python scripts/04_pass_a.py submit   [--dev|--rows 1,2,3] [--model sonnet|opus]   # shows estimate, asks y/N
  python scripts/04_pass_a.py collect  <batch_id>                                  # -> data/interim/pass_a/<row>.json

API notes (anthropic-version 2026-10-21; anthropic SDK 2.x):
- no temperature/top_p/top_k: they return a 400 on this version;
- citations cannot be combined with output_config.format (400), so the
  output is tagged plain text, parsed by aic.extract.parse_response;
- the server-side `fallbacks` parameter is rejected on Batches, so a
  `refusal` stop reason is recorded and the row goes to hand review;
- scanned PDFs are skipped until OCR'd (no text layer).
"""

import argparse
import hashlib
import json
import os
import random
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402
from aic.corpus import EXTRACTION_VERSION, doc_for_row  # noqa: E402
from aic.extract import CHARACTERISATIONS, parse_response  # noqa: E402
from aic.spend import ASK_ABOVE_USD, check_budget, record, spent  # noqa: E402

OUT = ROOT / "data/interim/pass_a"
MODELS = {  # US$ per 1M tokens, standard rates; Batches cost 50% of these
    "sonnet": ("claude-sonnet-5-5", 2.00, 10.00),  # the brief's original cost choice
    "opus": ("claude-opus-5-5", 4.00, 20.00),  # chosen by Luc on 25 Oct 2026 (D009)
}
BATCH_DISCOUNT = 0.5
MAX_TOKENS = 16000
EST_CHARS_PER_TOKEN = 3.5  # fallback only; count_tokens (free) is used when a key exists
EST_OUTPUT_TOKENS = 3000  # per document incl. thinking; the 10-document dev run averaged 1,970 (25 Oct 2026)
DEV_SEED = 20261025
DEV_STRATA = {"Lawyer": 4, "Pro Se Litigant": 4, "other": 1, "docx": 1}


SYSTEM = f"""You extract evidence from one Australian court or tribunal decision about \
generative AI producing false or inaccurate material in that proceeding.

Write one finding per line. Start each line with a tag in square brackets, then a \
short neutral description. Support every line with a citation to the passage of the \
decision it rests on, citing the narrowest passage that supports it. Write nothing \
the decision does not say. Do not add names, facts or inferences from outside the \
document. If the decision does not address an item, omit that tag.

Tags:
[MNC] the decision's own medium neutral citation, as printed.
[TITLE] the decision's title exactly as printed (anonymised titles stay anonymised).
[DATE] the date of the decision, as printed.
[COURT] the court or tribunal, as printed.
[PARTY] who put the affected material before the court: lawyer, self-represented \
litigant, expert, judicial officer, or other, as the decision describes them.
[AI_USE] whether the decision says AI use was admitted, found by the court, suspected, \
or denied.
[AI_TOOL] the AI tool, only if the decision names one.
[AI_ERROR] what went wrong, e.g. citing cases that do not exist.
[IMPUGNED] one line per distinct citation that the decision says was false or \
inaccurate in material filed or relied on in THIS proceeding. Do not include \
citations from other cases that the decision merely discusses. Format: \
[IMPUGNED] <the citation exactly as the decision reproduces it> || <characterisation> \
where characterisation is one of: {", ".join(CHARACTERISATIONS)}. \
Use non_existent only if the decision says the authority does not exist; not_located \
if it says only that it could not be found; not_stated if it does not say what was wrong.
[CONSEQUENCE] what the court did about it (e.g. costs, referral, warning, submissions \
disregarded, dismissal, leave refused, or no consequence).
[REFERRAL] any referral to a regulator (e.g. a Legal Services Commissioner or legal \
practice board), or a direction that the reasons be sent to one.
[PRACTICE_NOTE] any practice note, practice direction or guideline on AI that the \
decision cites, with the paragraph it cites, if any.

Write plain lines only: no headings, no markdown, no commentary before or after."""

USER_INSTRUCTION = ("Extract the findings from the decision above: one tagged line per finding, "
                    "each supported by a citation.")


def load_docs() -> pd.DataFrame:
    man = pd.read_csv(ROOT / "data/interim/doc_manifest.csv", dtype=str, keep_default_na=False)
    meta = pd.read_csv(ROOT / "data/interim/doc_metadata.csv", dtype=str, keep_default_na=False)
    cases = pd.read_csv(ROOT / "data/interim/au_cases.csv", dtype=str, keep_default_na=False)
    d = man[man.status == "200"].merge(meta[["charlotin_row", "scanned"]], on="charlotin_row") \
        .merge(cases[["charlotin_row", "Party(ies)"]], on="charlotin_row")
    return d.reset_index(drop=True)


def dev_sample(docs: pd.DataFrame) -> pd.DataFrame:
    """Fixed, stratified 10-document sample: 4 lawyer, 4 self-represented, 1 other party, 1 .docx."""
    rng = random.Random(DEV_SEED)
    pdf = docs[(docs.local_file.str.endswith(".pdf")) & (docs.scanned != "True")]
    picks = []
    for stratum, n in DEV_STRATA.items():
        if stratum == "docx":
            pool = docs[docs.local_file.str.endswith(".docx")]
        elif stratum == "other":
            pool = pdf[~pdf["Party(ies)"].isin(["Lawyer", "Pro Se Litigant"])]
        else:
            pool = pdf[pdf["Party(ies)"] == stratum]
        rows = sorted(pool.charlotin_row, key=int)
        picks += rng.sample(rows, n)
    return docs[docs.charlotin_row.isin(picks)]


def document_block(text: str, row: str) -> dict:
    return {"type": "document", "source": {"type": "text", "media_type": "text/plain", "data": text},
            "title": f"charlotin_row_{row}", "citations": {"enabled": True}}


def request_params(text: str, row: str, model: str) -> dict:
    return {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": SYSTEM,
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": "high"},
        "messages": [{"role": "user", "content": [document_block(text, row),
                                                    {"type": "text", "text": USER_INSTRUCTION}]}],
    }


def estimate(docs: pd.DataFrame, texts: dict[str, str], model_key: str, client=None) -> float:
    model, p_in, p_out = MODELS[model_key]
    in_tok = 0
    for _, d in docs.iterrows():
        p = request_params(texts[d.charlotin_row], d.charlotin_row, model)
        if client:
            in_tok += client.messages.count_tokens(model=model, system=p["system"], messages=p["messages"],
                                                   thinking=p["thinking"]).input_tokens
        else:
            in_tok += int(len(texts[d.charlotin_row]) / EST_CHARS_PER_TOKEN) + 1500
    out_tok = EST_OUTPUT_TOKENS * len(docs)
    method = "count_tokens API" if client else f"~{EST_CHARS_PER_TOKEN} chars/token heuristic"
    print(f"{len(docs)} documents | input = {in_tok:,} tokens ({method}) | output ≈ {out_tok:,} tokens (assumed)")
    for key, (mname, pi, po) in MODELS.items():
        c = (in_tok * pi + out_tok * po) / 1e6 * BATCH_DISCOUNT
        print(f"  {mname:<18} via Batches: ≈ US${c:.2f}" + ("   <- selected" if key == model_key else ""))
    return (in_tok * p_in + out_tok * p_out) / 1e6 * BATCH_DISCOUNT


def collect(batch_id: str) -> None:
    import anthropic

    client = anthropic.Anthropic()
    log = {json.loads(x)["batch_id"]: json.loads(x) for x in (OUT / "batches.jsonl").read_text().splitlines()}
    model = log.get(batch_id, {}).get("model", "")
    n, rows_seen = 0, []
    for r in client.messages.batches.results(batch_id):
        row = r.custom_id.removeprefix("row-")
        rows_seen.append(row)
        rec = {"charlotin_row": row, "batch_id": batch_id, "model": model, "result_type": r.result.type}
        if r.result.type == "succeeded":
            msg = r.result.message
            rec.update(model=msg.model, stop_reason=msg.stop_reason, usage=msg.usage.to_dict())
            if msg.stop_reason == "refusal":
                details = getattr(msg, "stop_details", None)
                rec["needs_hand_review"] = f"refusal: {getattr(details, 'category', None)}"
            else:
                rec["raw_text"], rec["findings"] = parse_response(msg.content)
                if msg.stop_reason == "max_tokens":
                    rec["needs_hand_review"] = "truncated (max_tokens)"
        elif r.result.type == "errored":
            rec["error"] = str(r.result.error)
        (OUT / f"{row}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False))
        n += 1
    usages = [json.loads((OUT / f"{r}.json").read_text()).get("usage") for r in rows_seen]
    cost = record(batch_id, "04_pass_a", model or MODELS["opus"][0], [u for u in usages if u])
    print(f"collected {n} results into {OUT}; actual cost US${cost:.2f}; project total US${spent():.2f}")


def main() -> None:
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["estimate", "submit", "collect"])
    ap.add_argument("batch_id", nargs="?")
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--rows", help="comma-separated charlotin_row values")
    ap.add_argument("--model", choices=list(MODELS), default="opus")  # Luc chose Opus 5.5 (D009)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.cmd == "collect":
        return collect(a.batch_id)

    docs = load_docs()
    skipped = docs[docs.scanned == "True"]
    if len(skipped):
        print(f"Skipping {len(skipped)} scanned PDF(s) until OCR'd: rows {', '.join(skipped.charlotin_row)}")
    if a.dev:
        docs = dev_sample(docs)
        docs[["charlotin_row", "Party(ies)", "local_file"]].to_csv(OUT / "dev_sample.csv", index=False)
    elif a.rows:
        docs = docs[docs.charlotin_row.isin(a.rows.split(",")) & (docs.scanned != "True")]
    else:
        docs = docs[docs.scanned != "True"]
    texts = {d.charlotin_row: doc_for_row(d.charlotin_row, d.local_file).text for _, d in docs.iterrows()}
    done = {p.stem for p in OUT.glob("*.json")}
    if done & set(docs.charlotin_row):
        print(f"Note: {len(done & set(docs.charlotin_row))} of these already have results in {OUT}")

    import anthropic

    client = anthropic.Anthropic() if os.environ.get("ANTHROPIC_API_KEY") else None
    cost = estimate(docs, texts, a.model, client)
    if a.cmd == "estimate":
        return
    if not client:
        sys.exit("No ANTHROPIC_API_KEY in .env; cannot submit.")
    model = MODELS[a.model][0]
    if reason := check_budget(cost):
        sys.exit(f"Refused: {reason}.")
    print(f"Project spend so far: US${spent():.2f} of US$30."
          + (f" This batch is over US${ASK_ABOVE_USD:.0f}: Luc's explicit yes is required."
             if cost > ASK_ABOVE_USD else ""))
    if input(f"Submit {len(docs)} requests to {model} (≈US${cost:.2f})? [y/N] ").strip().lower() != "y":
        sys.exit("Not submitted.")
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    reqs = [Request(custom_id=f"row-{d.charlotin_row}",
                    params=MessageCreateParamsNonStreaming(**request_params(texts[d.charlotin_row],
                                                                            d.charlotin_row, model)))
            for _, d in docs.iterrows()]
    batch = client.messages.batches.create(requests=reqs)
    sent = OUT / "sent_text.csv"
    new_rows = pd.DataFrame([{"charlotin_row": r, "batch_id": batch.id, "chars": len(t),
                              "text_sha256": hashlib.sha256(t.encode("utf-8")).hexdigest(),
                              "extraction_version": EXTRACTION_VERSION} for r, t in texts.items()])
    pd.concat([pd.read_csv(sent, dtype=str), new_rows] if sent.exists() else [new_rows]).to_csv(sent, index=False)
    with (OUT / "batches.jsonl").open("a") as f:
        f.write(json.dumps({"batch_id": batch.id, "n": len(reqs), "dev": a.dev, "model": model,
                            "estimate_usd": round(cost, 2)}) + "\n")
    print(f"Submitted batch {batch.id}. Collect with: python scripts/04_pass_a.py collect {batch.id}")


if __name__ == "__main__":
    main()
