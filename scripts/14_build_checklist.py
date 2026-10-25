"""Build the one-page verification checklist (site/checklist.html and site/checklist.pdf).

Rules for this page (brief): it cites only paragraphs that are in the rules
matrix, and its one figure comes from data/stats.json (computed from the
tracker). The build fails if a cited paragraph is not in
data/reference/rules_evidence.csv for that instrument.

The PDF is printed from the HTML by headless Chrome (A4, one page).

Text status: draft by Claude, to be edited by Luc (LUC 1.5 h).
"""

import csv
import html
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
LABEL = {  # citation label -> evidence source key
    "NSW SC Gen 23": "nsw_sc_gen23", "Vic SC Gen 25": "vic_sc_gen25_current", "Vic SC Gen 26": "vic_sc_gen26",
    "Qld SC PD 5/2025": "qld_sc_pd5_2025_current", "WA SC PD 9.21": "wa_sc_cpd_20260925",
}
MANDATED = ('A tool returning "found" means a record with this citation and these party names exists. '
            "It is not verification under Vic SC Gen 25 para 7 or NSW SC Gen 23 paras 16–17. "
            "Open the source and read the cited passage.")
# Each item: (heading, text). Citations are written {Label para,para}.
ITEMS = [
    ("Find the rules", "Identify the court's instrument in the matrix. Several courts bind self-represented "
     "litigants and experts as well as lawyers {WA SC PD 9.21 1} {Vic SC Gen 25 2.2}."),
    ("Open every case", "Open each authority from an authoritative source. Check that the party names, year, court and "
     "number match. Then read the cited paragraph and confirm it supports the proposition {Vic SC Gen 25 7.4}."),
    ("Check quotes and pinpoints", "Compare every quotation word for word with the source, and check that the pinpoint "
     "points to the passage relied on {Vic SC Gen 25 7.4}."),
    ("Check legislation", "Confirm that each Act and section exists and says what is claimed, using an authorised "
     "legislation website {Vic SC Gen 25 7.4}."),
    ("Do not check AI with AI", "Asking an AI tool whether a case exists is not verification {NSW SC Gen 23 17} "
     "{Vic SC Gen 25 7.4}."),
    ("A 'found' result is not verification", MANDATED),
    ("Evidence is different", "AI must not generate the content of affidavits or witness statements in NSW, and they "
     "must say so {NSW SC Gen 23 10,13}; elsewhere they must reflect the witness's own words {Vic SC Gen 25 6.11} "
     "{WA SC PD 9.21 11}."),
    ("Protect confidential material", "Do not put suppressed, subpoenaed or confidential material into public AI tools "
     "{NSW SC Gen 23 9A} {Vic SC Gen 25 6.8} {WA SC PD 9.21 10}."),
    ("Record who checked", "In NSW the author verifies the references in the body of the submissions "
     "{NSW SC Gen 23 16}. In Queensland the responsible practitioner is named, not just the firm "
     "{Qld SC PD 5/2025 5,6}. Be ready to show which parts used AI and how they were checked {Vic SC Gen 25 7.6}, "
     "and disclose AI use where directed or appropriate {WA SC PD 9.21 12}."),
]
CITE = re.compile(r"\{(.+?) ([0-9A-Z.,]+)\}")


def evidence_paras() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for e in csv.DictReader((ROOT / "data/reference/rules_evidence.csv").open()):
        out.setdefault(e["source_key"], set()).add(e["paragraph"])
    return out


def render(text: str, paras: dict[str, set[str]]) -> str:
    def sub(m: re.Match) -> str:
        label, refs = m.group(1), m.group(2).split(",")
        key = LABEL[label]
        missing = [r for r in refs if r not in paras.get(key, set())]
        if missing:
            raise SystemExit(f"Checklist cites {label} para {missing}, which is not in the rules matrix.")
        return f'<span class="cite">({html.escape(label)} para{"s" if len(refs) > 1 else ""} {", ".join(refs)})</span>'
    # Escape the prose but keep the citation markers for substitution.
    parts, last, out = list(CITE.finditer(text)), 0, ""
    for m in parts:
        out += html.escape(text[last:m.start()]) + sub(m)
        last = m.end()
    return out + html.escape(text[last:])


def main() -> None:
    paras = evidence_paras()
    stats = json.loads((ROOT / "data/stats.json").read_text())
    share = stats["share_misrepresentation_or_false_quote"]
    stat_html = (f"Of the {share['denominator']} Australian decisions verified so far that record what went wrong, "
                 f"{share['numerator']} ({share['percent']}%) involved a real authority misdescribed or a false quote, "
                 "not only a case that does not exist. Checking that a case exists is not enough."
                 if share["denominator"] else "[Statistic pending: computed from the tracker once rows are verified.]")
    items = "\n".join(f'<li><strong>{html.escape(h)}.</strong> {render(t, paras)}</li>' for h, t in ITEMS)
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Citation Checklist</title>
<style>
  @page {{ size: A4; margin: 14mm 15mm; }}
  :root {{ --fg:#1b1b19; --muted:#5d5d58; --line:#d9d6cc; --accent:#2c4f7c; --bg:#ffffff; }}
  @media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --fg:#ecebe6; --muted:#a6a49c; --line:#3a3934; --accent:#8fb1de; --bg:#161614; }} }}
  @media print {{ :root {{ --fg:#1b1b19; --muted:#5d5d58; --line:#d9d6cc; --accent:#2c4f7c; --bg:#ffffff; }} }}
  body {{ margin: 0 auto; max-width: 780px; padding: 16px; font: 10.4pt/1.42 -apple-system, "Helvetica Neue", Arial, sans-serif; color: var(--fg); background: var(--bg); }}
  h1 {{ font-size: 16pt; margin: 0 0 2px; }}
  .sub {{ color: var(--muted); margin: 0 0 10px; }}
  ol {{ padding-left: 20px; margin: 8px 0; }} li {{ margin: 0 0 6px; }}
  .cite {{ color: var(--accent); white-space: nowrap; font-size: 9pt; }}
  .stat {{ border-left: 3px solid var(--accent); padding: 6px 10px; margin: 10px 0; }}
  footer {{ color: var(--muted); font-size: 8.4pt; border-top: 1px solid var(--line); padding-top: 6px; margin-top: 10px; }}
</style></head>
<body>
<h1>Checking AI-assisted citations before filing</h1>
<p class="sub">A one-page checklist for paralegals in Australian courts. Rules as at 25 October 2026.</p>
<div class="stat">{stat_html}</div>
<ol>
{items}
</ol>
<footer>Not legal advice. Paragraph references are to the official instruments in the AI in Australian Courts
rules matrix; check the current version before relying on them. The statistic is computed by script from the
tracker, which builds on Damien Charlotin's AI Hallucination Cases database (CC BY 4.0).
Luc Taya, Economics (Honours) graduate, University of Western Australia. CC BY 4.0.</footer>
</body></html>
"""
    out = ROOT / "site"
    out.mkdir(exist_ok=True)
    (out / "checklist.html").write_text(page)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={out / 'checklist.pdf'}", (out / "checklist.html").as_uri()],
                   check=True, capture_output=True)
    print(f"wrote {out / 'checklist.html'} and {out / 'checklist.pdf'}")


if __name__ == "__main__":
    main()
