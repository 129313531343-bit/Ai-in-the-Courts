"""Local review page for Luc's spot-check (http://127.0.0.1:8765).

Serves review/review.html and these endpoints:
  GET  /api/queue           rows in data/review/luc_queue.csv with fields, quotes, checks and links
  POST /api/decision/<row>  saves Luc's decision to data/review/decisions/<row>.json
  GET/POST /api/answers     Luc's answers to the open questions (data/review/luc_answers.json, local only)
  GET  /api/rules           rules-matrix cells with their supporting quotes and paragraphs
  POST /api/rules_decision  saves Luc's check of the rules cells (data/review/rules_decisions.json)

Bound to 127.0.0.1 only: nothing is reachable from other machines. Judgment
text never leaves this machine; the page shows only the verified quotes.

Usage: python scripts/13_review_server.py   (then open http://127.0.0.1:8765)
"""

import json
import re
import sys
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402
from aic.courts import courts  # noqa: E402

PORT = 8765
DECISIONS = ROOT / "data/review/decisions"
ANSWERS = ROOT / "data/review/luc_answers.json"
RULES_DECISIONS = ROOT / "data/review/rules_decisions.json"
RULE_COLUMNS = ["who_is_bound", "disclosure_duty", "banned_or_cautioned_uses", "verification_duty", "consequences"]
JUR = {"Cth": "cth", "NSW": "nsw", "Vic": "vic", "Qld": "qld", "WA": "wa", "SA": "sa", "Tas": "tas", "ACT": "act",
       "NT": "nt"}
MNC = re.compile(r"\[(\d{4})\] (\S+) (\d+)")


def links(mnc: str) -> dict:
    """Links for a person to click. Formats are for Luc to confirm (brief); nothing here is fetched."""
    m = MNC.match(mnc or "")
    if not m or m.group(2) not in courts():
        return {}
    year, code, num = m.groups()
    jur = JUR.get(courts()[code].jurisdiction, "")
    return {"AustLII (unconfirmed format)": f"https://www.austlii.edu.au/cgi-bin/viewdoc/au/cases/{jur}/{code}/{year}/{num}.html"}


def rules() -> list[dict]:
    """Each drafted instrument with its cells and the verified quotes behind them."""
    import csv

    draft = list(csv.DictReader((ROOT / "data/reference/rules_draft.csv").open()))
    evidence = list(csv.DictReader((ROOT / "data/reference/rules_evidence.csv").open()))
    decided = json.loads(RULES_DECISIONS.read_text()) if RULES_DECISIONS.exists() else {}
    out = []
    for d in draft:
        same_as = d["evidence_from"] if d["evidence_from"] != d["source_key"] else ""
        cells = [{"column": c, "text": d[c],
                  "evidence": [{"paragraph": e["paragraph"], "quote": e["quote"]} for e in evidence
                               if e["source_key"] == d["evidence_from"] and e["column"] == c]} for c in RULE_COLUMNS]
        out.append({"key": d["key"], "court": d["court"], "instrument": d["instrument"], "url": d["url"],
                    "issued": d["issued"], "same_as": same_as, "cells": cells, "decision": decided.get(d["key"])})
    return out


def queue() -> list[dict]:
    q = pd.read_csv(ROOT / "data/review/luc_queue.csv", dtype=str, keep_default_na=False)
    cases = pd.read_csv(ROOT / "data/interim/au_cases.csv", dtype=str, keep_default_na=False).set_index("charlotin_row")
    meta = pd.read_csv(ROOT / "data/interim/doc_metadata.csv", dtype=str, keep_default_na=False) \
        .set_index("charlotin_row")
    qc_path = ROOT / "data/interim/quote_checks.csv"
    qc = pd.read_csv(qc_path, dtype=str, keep_default_na=False) if qc_path.exists() else pd.DataFrame(
        columns=["charlotin_row"])
    vc_path = ROOT / "data/interim/verification_checks.csv"
    vc = pd.read_csv(vc_path, dtype=str, keep_default_na=False) if vc_path.exists() else pd.DataFrame(
        columns=["charlotin_row"])
    ids = dict(pd.read_csv(ROOT / "data/reference/id_map.csv", dtype=str).values) \
        if (ROOT / "data/reference/id_map.csv").exists() else {}
    out = []
    for _, r in q.iterrows():
        row = r.charlotin_row
        c = cases.loc[row]
        pb_path = ROOT / f"data/interim/pass_b/{row}.json"
        pb = json.loads(pb_path.read_text()) if pb_path.exists() else {}
        quotes = {x.quote_id: {"text": x.cited_text, "page": x.page, "paragraph": x.paragraph, "pass": x["pass"]}
                  for _, x in qc[qc.charlotin_row == row].iterrows()}
        dec_path = DECISIONS / f"{row}.json"
        mnc = meta.loc[row, "mnc_from_document"] if row in meta.index else c["mnc_proposed"]
        out.append({
            "row": row, "id": ids.get(row, ""), "status": r.verification_status, "reason": r.reason,
            "task": r.get("task", ""), "priority": r.get("priority", ""),
            "random_spot_check": r.in_random_spot_check == "True", "mnc": mnc,
            "court": meta.loc[row, "court"] if row in meta.index else c["Court"],
            "date": c["Date"], "source_kind": c["source_kind"], "source_url": c["source_url"],
            "copy": meta.loc[row, "copy_source_markers"] if row in meta.index else "",
            "charlotin": {"party": c["Party(ies)"], "outcome": c["Outcome"], "case_name": c["Case Name"]},
            "fields": pb.get("fields", {}), "dropped": pb.get("dropped_unsupported", []),
            "quotes": quotes, "links": links(mnc),
            "checks": [{"check": x.check, "passed": x.passed == "True", "detail": x.detail}
                       for _, x in vc[vc.charlotin_row == row].iterrows()],
            "decision": json.loads(dec_path.read_text()) if dec_path.exists() else None,
        })
    return out


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/index.html"):
            self._send(200, (ROOT / "review/review.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/queue":
            self._send(200, json.dumps(queue()).encode(), "application/json")
        elif self.path == "/api/rules":
            self._send(200, json.dumps(rules()).encode(), "application/json")
        elif self.path == "/api/answers":
            self._send(200, ANSWERS.read_bytes() if ANSWERS.exists() else b"{}", "application/json")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/answers":
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            body["answered_on"] = date.today().isoformat()
            ANSWERS.parent.mkdir(parents=True, exist_ok=True)
            ANSWERS.write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n")
            return self._send(200, b'{"saved": true}', "application/json")
        if self.path == "/api/rules_decision":
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            decided = json.loads(RULES_DECISIONS.read_text()) if RULES_DECISIONS.exists() else {}
            decided[body["key"]] = {"cells": body["cells"], "reviewed_on": date.today().isoformat()}
            RULES_DECISIONS.parent.mkdir(parents=True, exist_ok=True)
            RULES_DECISIONS.write_text(json.dumps(decided, indent=2, ensure_ascii=False) + "\n")
            return self._send(200, b'{"saved": true}', "application/json")
        m = re.fullmatch(r"/api/decision/(\d+)", self.path)
        if not m:
            return self._send(404, b"not found", "text/plain")
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        body["reviewed_on"] = date.today().isoformat()
        DECISIONS.mkdir(parents=True, exist_ok=True)
        (DECISIONS / f"{m.group(1)}.json").write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n")
        self._send(200, b'{"saved": true}', "application/json")

    def log_message(self, *args) -> None:  # keep the terminal quiet
        pass


if __name__ == "__main__":
    print(f"Review page: http://127.0.0.1:{PORT}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
