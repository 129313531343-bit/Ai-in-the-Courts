"""Pass B: propose tracker field values from verified Pass A quotes only.

No judgment is sent. Claude sees only the Pass A quotes that 05_verify_quotes.py
found in the judgment text, as plain text with their IDs, and returns JSON
matching aic.extract.pass_b_schema() (structured outputs). Every value must
name the quote IDs it rests on; a field no quote supports is left blank.
Afterwards this script blanks any value whose quote IDs are missing or
unknown (aic.extract.enforce_quotes) rather than trusting it.

Plain text is used because API version 2026-10-21 rejects text blocks with
citations in a user turn, and citations cannot be combined with
output_config.format.

Usage:
  python scripts/06_pass_b.py estimate [--model sonnet|opus]
  python scripts/06_pass_b.py submit   [--model sonnet|opus]
  python scripts/06_pass_b.py collect <batch_id>      # -> data/interim/pass_b/<row>.json
"""

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402
from aic.extract import enforce_quotes, pass_b_schema  # noqa: E402
from aic.spend import ASK_ABOVE_USD, check_budget, record, spent  # noqa: E402

OUT = ROOT / "data/interim/pass_b"
MODELS = {"sonnet": ("claude-sonnet-5-5", 2.00, 10.00), "opus": ("claude-opus-5-5", 4.00, 20.00)}
BATCH_DISCOUNT = 0.5
EST_OUTPUT_TOKENS = 3000  # assumption, including thinking

SYSTEM = """You fill in a structured record about one Australian court decision, using ONLY \
the numbered quotes provided. The quotes are verbatim passages from the decision.

Rules:
- Every value must be supported by the quotes whose IDs you list in quote_ids.
- If no quote supports a field, leave its value empty ("" or []) and its quote_ids empty.
- Copy the MNC, title, citations and AI tool name exactly as they appear in the quotes. \
Never reconstruct, expand or complete a name or citation.
- title_as_published: the title exactly as the quotes show it; anonymised titles stay anonymised.
- ai_use: "admitted" or "found_by_court" only if a quote says so; "suspected" if the court \
only suspects AI was used.
- impugned_citations: only citations the quotes say were false or inaccurate in material \
filed or relied on in this proceeding, not citations from other cases the decision discusses. \
Use "non_existent" only if a quote says the authority does not exist; "not_located" if it \
says only that it could not be found. asserted_by: "court" if the court itself says the citation \
is false or inaccurate; "party" if the quotes only report a party's contention; otherwise "unclear".
- regulator_referred: "yes" only if a quote shows a referral or a direction to refer; \
"no_stated" only if a quote says there will be no referral.
- family_law_matter: "yes" only if a quote shows proceedings under family law legislation; \
"no" if a quote shows a different area of law; otherwise "unclear"."""


def load_checks() -> pd.DataFrame:
    c = pd.read_csv(ROOT / "data/interim/quote_checks.csv", dtype=str, keep_default_na=False)
    c["pass"] = c["pass"] == "True"
    return c


def quotes_text(q: pd.DataFrame) -> str:
    lines = []
    for _, r in q.iterrows():
        loc = ", ".join(x for x in (f"p {r.page}" if r.page else "", f"para {r.paragraph}" if r.paragraph else "")
                        if x)
        lines.append(f"{r.quote_id} ({loc + '; ' if loc else ''}Pass A tag {r.tag}): {r.cited_text}")
    return "\n\n".join(lines)


def request_params(qtext: str, model: str) -> dict:
    return {"model": model, "max_tokens": 16000, "system": SYSTEM, "thinking": {"type": "adaptive"},
            "output_config": {"effort": "high", "format": {"type": "json_schema", "schema": pass_b_schema()}},
            "messages": [{"role": "user", "content": f"Quotes from the decision:\n\n{qtext}"}]}


def collect(batch_id: str, checks: pd.DataFrame) -> None:
    import anthropic

    client = anthropic.Anthropic()
    usages, model = [], MODELS["opus"][0]
    for r in client.messages.batches.results(batch_id):
        row = r.custom_id.removeprefix("row-")
        rec = {"charlotin_row": row, "batch_id": batch_id, "result_type": r.result.type}
        if r.result.type == "succeeded":
            usages.append(r.result.message.usage.to_dict())
            model = r.result.message.model
        if r.result.type == "succeeded":
            msg = r.result.message
            rec.update(model=msg.model, stop_reason=msg.stop_reason, usage=msg.usage.to_dict())
            if msg.stop_reason == "refusal":
                rec["needs_hand_review"] = "refusal"
            elif msg.stop_reason == "max_tokens":
                rec["needs_hand_review"] = "truncated (max_tokens)"
            else:
                text = next(b.text for b in msg.content if b.type == "text")
                valid = set(checks[(checks.charlotin_row == row) & checks["pass"]].quote_id)
                rec["fields"], rec["dropped_unsupported"] = enforce_quotes(json.loads(text), valid)
        elif r.result.type == "errored":
            rec["error"] = str(r.result.error)
        (OUT / f"{row}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False))
    cost = record(batch_id, "06_pass_b", model, usages)
    print(f"collected into {OUT}; actual cost US${cost:.2f}; project total US${spent():.2f}")


def main() -> None:
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["estimate", "submit", "collect"])
    ap.add_argument("batch_id", nargs="?")
    ap.add_argument("--model", choices=list(MODELS), default="opus")  # Luc chose Opus 5.5 (D009)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    checks = load_checks()
    if a.cmd == "collect":
        return collect(a.batch_id, checks)

    passed = checks[checks["pass"]]
    done = {q.stem for q in OUT.glob("*.json") if json.loads(q.read_text()).get("fields")}
    texts = {row: quotes_text(g) for row, g in passed.groupby("charlotin_row") if row not in done}
    if done:
        print(f"Skipping {len(done)} rows that already have Pass B results.")
    in_tok = sum(len(t) // 4 + 2000 for t in texts.values())  # ~4 chars/token, plus system prompt and schema
    out_tok = EST_OUTPUT_TOKENS * len(texts)
    print(f"{len(texts)} documents | input ≈ {in_tok:,} tokens (heuristic) | output ≈ {out_tok:,} (assumed)")
    for key, (mname, pi, po) in MODELS.items():
        c = (in_tok * pi + out_tok * po) / 1e6 * BATCH_DISCOUNT
        print(f"  {mname:<18} via Batches: ≈ US${c:.2f}" + ("   <- selected" if key == a.model else ""))
    model, pi, po = MODELS[a.model]
    cost = (in_tok * pi + out_tok * po) / 1e6 * BATCH_DISCOUNT
    if a.cmd == "estimate":
        return
    if reason := check_budget(cost):
        sys.exit(f"Refused: {reason}.")
    print(f"Project spend so far: US${spent():.2f} of US$30."
          + (f" This batch is over US${ASK_ABOVE_USD:.0f}: Luc's explicit yes is required."
             if cost > ASK_ABOVE_USD else ""))
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("No ANTHROPIC_API_KEY in .env; cannot submit.")
    if input(f"Submit {len(texts)} requests to {model} (≈US${cost:.2f})? [y/N] ").strip().lower() != "y":
        sys.exit("Not submitted.")
    import anthropic
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    batch = anthropic.Anthropic().messages.batches.create(requests=[
        Request(custom_id=f"row-{row}", params=MessageCreateParamsNonStreaming(**request_params(t, model)))
        for row, t in texts.items()])
    with (OUT / "batches.jsonl").open("a") as f:
        f.write(json.dumps({"batch_id": batch.id, "n": len(texts), "model": model,
                            "estimate_usd": round(cost, 2)}) + "\n")
    print(f"Submitted {batch.id}. Collect with: python scripts/06_pass_b.py collect {batch.id}")


if __name__ == "__main__":
    main()
