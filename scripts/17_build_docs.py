"""Build the methods paper (docs/methods.html, docs/methods.pdf) and the practice-note
fact pack (private/factpack.md). Every figure is computed here from the data.

The methods paper is a DRAFT for Luc to check; it will be public. The fact pack
is for Luc's own writing, holds provisional figures, and stays private.
"""

import csv
import html
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402
from aic.spend import spent  # noqa: E402

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
AUTHOR = "Luc Taya, Economics (Honours) graduate, University of Western Australia"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson 95% interval for a proportion k/n."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return ((c - r) / d, (c + r) / d)


def figures() -> dict:
    f = {}
    au = json.loads((ROOT / "data/interim/au_summary.json").read_text())
    f["download_rows"], f["au_rows"] = au["rows_in_download"], au["australian_rows"]
    f["date_from"], f["date_to"] = au["decision_dates"]
    meta = pd.read_csv(ROOT / "data/interim/doc_metadata.csv", dtype=str, keep_default_na=False)
    f["docs"] = len(meta)
    f["austlii"] = int(meta.copy_source_markers.str.contains("AustLII").sum())
    f["wikisource"] = int(meta.copy_source_markers.str.contains("Wikisource").sum())
    f["scanned"] = int((meta.scanned == "True").sum())
    f["own_mnc"] = int((meta.mnc_from_document != "").sum())
    f["pages"] = int(pd.to_numeric(meta.n_pages, errors="coerce").sum())
    q = pd.read_csv(ROOT / "data/interim/quote_checks.csv", dtype=str, keep_default_na=False)
    f["quotes"], f["quotes_exact"] = len(q), int((q.method == "exact_offset").sum())
    f["quote_docs"] = q.charlotin_row.nunique()
    st = pd.read_csv(ROOT / "data/interim/row_status.csv", dtype=str, keep_default_na=False)
    f["status"] = st.verification_status.value_counts().to_dict()
    spot = pd.read_csv(ROOT / "data/review/spot_check_sample.csv", dtype=str)
    f["spot_n"], f["spot_pop"], f["spot_seed"] = len(spot), spot.population_size.iloc[0], spot.seed.iloc[0]
    # Luc's spot-check: accuracy of the fields that need judgement, reported apart from the header facts
    # (citation, title, court, date, family law), which were already matched by script.
    header = {"mnc", "title_as_published", "court", "date", "family_law_matter"}
    k = n = hk = hn = rows = unsure = clean = 0
    for r in spot.charlotin_row:
        p = ROOT / f"data/review/decisions/{r}.json"
        if not p.exists():
            continue
        rows += 1
        fields = json.loads(p.read_text())["fields"]
        clean += all(v["verdict"] == "correct" for x, v in fields.items() if x not in header)
        for x, v in fields.items():
            if v["verdict"] == "unsure":
                unsure += 1
            elif x in header:
                hn += 1
                hk += v["verdict"] == "correct"
            else:
                n += 1
                k += v["verdict"] == "correct"
    f.update(spot_done=rows, spot_fields=n, spot_correct=k, spot_ci=wilson(k, n), spot_unsure=unsure,
             spot_header=(hk, hn), spot_clean=clean)
    rules = list(csv.DictReader((ROOT / "data/interim/rules_evidence_checks.csv").open()))
    f["rule_quotes"], f["rule_quotes_ok"] = len(rules), sum(r["pass"] == "True" for r in rules)
    rd = ROOT / "data/review/rules_decisions.json"
    f["rules_checked"] = len(json.loads(rd.read_text())) if rd.exists() else 0
    rr = pd.read_csv(ROOT / "data/rules.csv", dtype=str, keep_default_na=False)
    src = pd.read_csv(ROOT / "data/interim/rules_sources.csv", dtype=str, keep_default_na=False)
    real = (rr.instrument != "") & (rr.instrument != "No specific AI guidance found")
    f["instruments"] = int(real.sum())
    f["by_browser"] = int((real & rr.url.isin(src.url[src.status.str.startswith("saved by")])).sum())
    f["no_guidance"] = int((rr.instrument == "No specific AI guidance found").sum())
    f["hand_pending"] = int((rr.instrument == "").sum())
    f["agreement"] = json.loads((ROOT / "data/interim/agreement.json").read_text())["party_type"]
    f["held"] = json.loads((ROOT / "data/stats.json").read_text()).get("rows_with_details_withheld_pending_austlii", 0)
    f["spend"] = spent()
    t = pd.read_csv(ROOT / "data/interim/tracker_full.csv", dtype=str, keep_default_na=False)
    f["tracker"] = t
    return f


def methods_html(f: dict) -> str:
    st, ag = f["status"], f["agreement"]
    # Claim only what the saved review data shows (5 instruments need checking; 2 reuse Qld PD 5).
    reviewed = "reviewed the random sample" if f["spot_done"] >= f["spot_n"] else "is reviewing the random sample"
    checked = "checked the rules matrix" if f["rules_checked"] >= 5 else "is checking the rules matrix"
    spot = (f"Results ({f['spot_done']} of {f['spot_n']} rows reviewed): of the fields that need judgement (party, AI use, "
            f"AI tool, error types, impugned citations, consequence, referral, practice note), {f['spot_correct']} of "
            f"{f['spot_fields']} were correct ({100 * f['spot_correct'] / f['spot_fields']:.1f}%; Wilson 95% interval "
            f"{100 * f['spot_ci'][0]:.1f}–{100 * f['spot_ci'][1]:.1f}%), with {f['spot_unsure']} marked unsure. "
            f"{f['spot_clean']} of {f['spot_done']} rows had every judgement field marked correct. The errors were omissions (a missing error type "
            "or citation) and over-calls, notably 'submissions disregarded' where the court had not disregarded them, and "
            "'found by the court' where the court only suspected AI use. The header facts were correct in "
            f"{f['spot_header'][0]} of {f['spot_header'][1]}. Corrections are applied before publication."
            if f["spot_fields"] else "[Results pending: the author's review of the random sample is in progress.]")
    e = html.escape
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Tracker Methods</title>
<style>
@page {{ size: A4; margin: 13mm 15mm; }}
:root {{ --fg:#1b1b19; --muted:#5d5d58; --line:#d9d6cc; --accent:#2c4f7c; --bg:#fff; --warn:#8a5a00; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --fg:#ecebe6; --muted:#a6a49c; --line:#3a3934; --accent:#8fb1de; --bg:#161614; --warn:#e0b45c; }} }}
@media print {{ :root {{ --fg:#1b1b19; --muted:#5d5d58; --line:#d9d6cc; --accent:#2c4f7c; --bg:#fff; --warn:#8a5a00; }} }}
body {{ margin:0 auto; max-width:800px; padding:16px; font:9.6pt/1.42 -apple-system, "Helvetica Neue", Arial, sans-serif; color:var(--fg); background:var(--bg); }}
h1 {{ font-size:15pt; margin:0 0 2px; }} h2 {{ font-size:10.6pt; margin:10px 0 3px; color:var(--accent); }}
p {{ margin:0 0 5px; }} ul {{ margin:2px 0 6px; padding-left:18px; }} li {{ margin:0 0 2px; }}
.sub {{ color:var(--muted); margin-bottom:8px; }}
.todo {{ border:1px solid var(--warn); border-left:4px solid var(--warn); padding:5px 8px; margin:6px 0; }}
table {{ border-collapse:collapse; font-size:9pt; margin:3px 0 6px; }} td, th {{ border-bottom:1px solid var(--line); padding:2px 8px 2px 0; text-align:left; }}
footer {{ color:var(--muted); font-size:8.4pt; border-top:1px solid var(--line); margin-top:8px; padding-top:5px; }}
</style></head><body>
<h1>AI in Australian Courts: how the data were built and checked</h1>
<p class="sub">Methods note, Release 1 (draft of 26 October 2026). {e(AUTHOR)}.</p>

<h2>1. What this covers</h2>
<p>Three outputs: a tracker of Australian decisions in which AI-generated false or inaccurate material reached a court or
tribunal; a matrix of court and tribunal rules on generative AI; and a one-page verification checklist. This note explains
the sources, the extraction, the checks and their limits. Every figure below is computed by script from the published data.</p>

<h2>2. Sources</h2>
<ul>
<li><strong>Cases.</strong> Damien Charlotin's AI Hallucination Cases database (CC BY 4.0), downloaded 25 October 2026:
{f['download_rows']:,} rows, of which {f['au_rows']} are Australian (decisions dated {e(f['date_from'])} to {e(f['date_to'])}).</li>
<li><strong>Judgments.</strong> The {f['docs']} copies the database hosts ({f['pages']:,} pages), fetched at one request every five
seconds and identified by SHA-256 hash. {f['austlii']} are printouts from AustLII and {f['wikisource']} is a Wikisource export, so
they are not authorised versions. {f['scanned']} is a scanned image with no text. AustLII and NSW Caselaw were never accessed
by code.</li>
<li><strong>Court rules.</strong> {f['instruments']} official practice notes, directions and guidance notes from the courts' and
tribunals' own websites: {f['instruments'] - f['by_browser']} fetched by script after checking each site's robots.txt, and
{f['by_browser']} saved in a browser because the site refuses automated requests. For {f['no_guidance']} more, no specific AI
guidance was found.{f" {f['hand_pending']} further instruments are still to be collected." if f['hand_pending'] else ""}</li>
</ul>
<div class="todo"><strong>Pending question (DECISIONS.md D007):</strong> whether processing the AustLII-printed copies with an AI
model is consistent with AustLII's terms is being put to AustLII. Until it replies, fields the model extracted from those copies are
not published ({f['held']} rows); rows the author checked against the judgment, facts read by script and Charlotin's coding are.</div>

<h2>3. Reading each judgment's basic facts (no AI)</h2>
<p>Each judgment's text was extracted locally. Running headers, page numbers and the publisher's banners and footers were removed,
and characters printed twice to fake bold were de-duplicated. A regular expression read the decision's own medium neutral citation
from its first pages ({f['own_mnc']} of {f['docs']} found), which gives the court and its level. Paragraph numbers were detected by
font size and position, keeping the longest run that counts up by one, so footnote numbers and numbered orders are excluded.</p>

<h2>4. Extraction with an AI model, in two passes</h2>
<ul>
<li><strong>Pass A, quotes:</strong> Claude Opus 5.5 (Anthropic), through the Message Batches API, read each judgment's text with
citations enabled. It returned tagged findings (the AI error, each impugned citation with the court's characterisation, the consequence,
any regulator referral, any practice note cited), each tied to the exact passage it rests on.</li>
<li><strong>Quote check:</strong> all {f['quotes']:,} quotes from the {f['quote_docs']} judgments were checked character for character
against the text that was sent ({f['quotes_exact']:,} matched exactly), then mapped to page and paragraph.</li>
<li><strong>Pass B, fields:</strong> the model proposed the tracker's fields from the verified quotes only, as structured output. Any
value not tied to a verified quote was discarded by code.</li>
</ul>

<h2>5. Automatic checks on every row</h2>
<p>Each row was checked against deterministic facts:
<ul>
<li>every value rests on a verified quote, with a paragraph number (or the orders);</li>
<li>the citation matches the judgment's header;</li>
<li>titles and impugned citations appear in the judgment;</li>
<li>each characterisation has textual support;</li>
<li>a citation the court did not itself impugn is flagged;</li>
<li>paragraph counts match the court's own certificate;</li>
<li>party type and referral are compared with Charlotin's coding.</li>
</ul>
Result: {st.get('auto_verified', 0)} rows passed every check (<em>auto-verified</em>), {st.get('flagged_for_review', 0)} were flagged,
{st.get('not_auto_verifiable', 0)} could not be checked automatically and {st.get('no_public_source', 0)} have no public judgment.
Party type agreed with Charlotin's coding in {ag['percent_agree']}% of {ag['n']} rows (Cohen's kappa {ag['cohen_kappa']}).
These checks prove that each value rests on real text at the stated paragraph; they cannot prove the text was read correctly.</p>

<h2>6. Human check</h2>
<p>A random sample of {f['spot_n']} rows was drawn and committed before any extraction (seed {e(str(f['spot_seed']))}, from
{e(str(f['spot_pop']))} eligible rows, excluding the 10 rows used to develop the prompts), so it could not be chosen to look good. The
author checks each field against the judgment. {spot} Rows not checked by a person publish only the facts read by script and
Charlotin's own coding, unless they are auto-verified and were not extracted from an AustLII-printed copy.</p>

<h2>7. Rules matrix</h2>
<p>Each cell is a plain-English summary backed by short quotations with paragraph numbers. A script confirmed that all
{f['rule_quotes_ok']} of {f['rule_quotes']} quotations appear in the official text inside the cited paragraph, reading paragraph spans
from each instrument's own numbering. The author checks each summary for fairness against its quotations.</p>

<h2>8. Privacy</h2>
<p>The tracker records only what each judgment says. Self-represented parties can be filtered but not searched, and their case titles
are not published; the public repository contains no self-represented party's name. Family law rows use only the court's anonymised title
(Family Law Act 1975 (Cth) s 114Q). Judgment text and quotations are not published.</p>

<h2>9. Limits</h2>
<ul>
<li>Coverage is only what Charlotin's database records. Labels and counts are relative to it, not to all Australian decisions.</li>
<li>Copies are not authorised versions. Readers should check the official source.</li>
<li>Auto-verification cannot detect a misreading; the human sample (n = {f['spot_n']}) is small, so its interval is wide.</li>
<li>Courts often decline to reproduce fabricated citations, so the impugned-citation lists are incomplete by design.</li>
</ul>

<h2>10. AI use and cost</h2>
<p>The pipeline, site and first drafts of the rules summaries, the checklist and this note were written with Claude Code (Anthropic),
an AI coding assistant. Claude models performed the extraction. The author designed the project, made and recorded the judgement calls,
{reviewed} and {checked}. Total API spend: US${f['spend']:.2f}.</p>
<footer>Code, data and decisions log: the project repository. Not legal advice. CC BY 4.0. {e(AUTHOR)}.</footer>
</body></html>"""


def factpack(f: dict) -> str:
    t = f["tracker"]
    pub = t[t.verification_status.isin(["auto_verified", "luc_spot_checked"])]
    n = len(pub)

    def count(col: str, val: str) -> int:
        return int(pub[col].str.split("; ").apply(lambda xs: val in xs).sum())

    lawyers = pub[pub.party_type == "lawyer"]
    non_ex = pub[pub.error_types.str.contains("non_existent_case")]
    not_repro = non_ex[non_ex.impugned_citations == ""]
    years = t.date.str[:4].value_counts().sort_index()
    lines = [
        "# Fact pack for the practice note (PRIVATE, provisional)",
        "",
        "For Luc's own writing. Every figure is computed by `scripts/17_build_docs.py`.",
        f"**Provisional:** figures marked [auto] come from the {n} rows that passed the automatic checks. That is not a random "
        f"sample (flagged rows are excluded){'' if f['spot_done'] >= f['spot_n'] else ', and Luc' + chr(39) + 's spot-check is not finished'}. "
        "**Do not publish any [auto] figure while "
        "D007 is open:** they come from AI processing of AustLII-printed copies. The Charlotin-coding and rules figures are fine. "
        "Re-run the script before quoting any number.",
        "",
        "## Scale (all Australian rows in Charlotin's database, downloaded 25 Oct 2026)",
        f"- {f['au_rows']} Australian decisions, out of {f['download_rows']:,} worldwide.",
        "- By year of decision: " + ", ".join(f"{y}: {c}" for y, c in years.items()) + ".",
        f"- Charlotin's party coding: {(t.charlotin_party_type == 'Pro Se Litigant').sum()} self-represented, "
        f"{(t.charlotin_party_type == 'Lawyer').sum()} lawyer.",
        "- By court level (read from each decision's own citation): "
        + ", ".join(f"{k or 'unknown'}: {v}" for k, v in t.court_level.value_counts().items()) + ".",
        "",
        f"## What courts found and did [auto, n = {n}]",
        f"- Non-existent cases cited: {count('error_types', 'non_existent_case')} rows; misdescribed real authorities: "
        f"{count('error_types', 'misdescribed_authority')}; false quotes: {count('error_types', 'false_quote')}.",
        f"- In {len(not_repro)} of the {len(non_ex)} rows where the court found non-existent cases, the decision "
        "reproduces none of the impugned citations (some judgments say expressly that they decline to). In the other "
        f"{len(non_ex) - len(not_repro)}, at least one impugned citation is reproduced.",
        f"- AI use: admitted {(pub.ai_use == 'admitted').sum()}, found by the court {(pub.ai_use == 'found_by_court').sum()}, "
        f"suspected only {(pub.ai_use == 'suspected').sum()}, denied {(pub.ai_use == 'denied').sum()}.",
        f"- An AI tool is named in {(pub.ai_tool_if_stated != '').sum()} rows.",
        f"- Lawyers ({len(lawyers)} rows): personal costs orders in "
        f"{int(lawyers.consequence.str.contains('personal_costs_order').sum())}; referral to a regulator in "
        f"{int((lawyers.regulator_referred == 'yes').sum())}.",
        f"- Applications or appeals dismissed: {count('consequence', 'application_or_appeal_dismissed')}; "
        f"warnings or admonishments: {count('consequence', 'warning_or_admonishment')}; "
        f"adverse costs orders: {count('consequence', 'adverse_costs_order')}.",
        f"- An AI practice note or direction is cited by the court in {(pub.practice_note_cited != '').sum()} rows.",
        "",
        "## What the rules say (official text, paragraph references verified)",
    ]
    rules = pd.read_csv(ROOT / "data/rules.csv", dtype=str, keep_default_na=False)
    for _, r in rules[rules.instrument != ""].iterrows():
        if r.instrument == "No specific AI guidance found":
            lines.append(f"- **{r.court}**: no specific AI guidance found (searched: {r.quotes_checked.removeprefix('searched: ')}).")
            continue
        lines.append(f"- **{r.instrument}** ({r.paragraph_refs}). Consequences: {r.consequences}")
    lines += ["", "## Method facts you can cite",
              f"- {f['quotes']:,} quotations extracted, all matched character for character in the judgment text.",
              f"- Pre-registered random human check of {f['spot_n']} rows (seed {f['spot_seed']}).",
              f"- Total API cost US${f['spend']:.2f}.", ""]
    return "\n".join(lines)


def main() -> None:
    f = figures()
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "methods.html").write_text(methods_html(f))
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={docs / 'methods.pdf'}", (docs / "methods.html").as_uri()],
                   check=True, capture_output=True)
    (ROOT / "private").mkdir(exist_ok=True)
    (ROOT / "private/factpack.md").write_text(factpack(f))
    print("wrote docs/methods.html, docs/methods.pdf and private/factpack.md")


if __name__ == "__main__":
    main()
