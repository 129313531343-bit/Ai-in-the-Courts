"""Build the static Release 1 site into site/ (deployed to Cloudflare Pages by Luc).

Pages: index, tracker (filters only: court, year, party type, consequence;
no free-text or name search), rules matrix, checklist (built by
14_build_checklist.py), about (methods, contributions and AI use, privacy,
corrections). Every number shown is read from data/ at build time.

Privacy (PRIVACY.md, D015): no party names in page titles, descriptions or
URLs; the tracker page and its data carry noindex; self-represented rows show
the MNC instead of the case title unless SHOW_SRL_TITLES is switched on (Luc's
decision, PRIVACY.md question 3).
"""

import html
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402

SITE = ROOT / "site"
SHOW_SRL_TITLES = False  # protective default until Luc decides (PRIVACY.md question 3)
AUTHOR = "Luc Taya, Economics (Honours) graduate, University of Western Australia"
CSS = """
:root { --bg:#fbfaf7; --fg:#1d1d1b; --muted:#66655f; --line:#e2dfd6; --card:#ffffff; --accent:#2c4f7c; --warn:#8a5a00; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg:#151513; --fg:#ecebe6; --muted:#a3a19a; --line:#33322e; --card:#1d1d1a; --accent:#8fb1de; --warn:#e0b45c; } }
:root[data-theme="dark"] { --bg:#151513; --fg:#ecebe6; --muted:#a3a19a; --line:#33322e; --card:#1d1d1a; --accent:#8fb1de; --warn:#e0b45c; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font:16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
a { color: var(--accent); }
header.site { border-bottom:1px solid var(--line); }
header.site .in, main, footer.site .in { max-width:1100px; margin:0 auto; padding:0 16px; }
header.site .in { display:flex; gap:20px; align-items:center; flex-wrap:wrap; padding-top:14px; padding-bottom:14px; }
header.site .brand { font-weight:700; text-decoration:none; color:var(--fg); }
header.site nav a { margin-right:14px; text-decoration:none; white-space:nowrap; display:inline-block; }
main { padding-top:24px; padding-bottom:40px; }
h1 { font-size:28px; line-height:1.2; margin:0 0 8px; } h2 { font-size:20px; margin:28px 0 8px; }
.lede { color:var(--muted); max-width:760px; }
.banner { border:1px solid var(--line); border-left:4px solid var(--warn); background:var(--card); padding:10px 14px; border-radius:6px; margin:16px 0; }
.cards { display:grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap:14px; margin:18px 0; }
.card { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:16px; }
.card .num { font-size:30px; font-weight:700; }
.muted { color:var(--muted); }
.filters { display:flex; flex-wrap:wrap; gap:10px; margin:14px 0; }
.filters label { font-size:14px; color:var(--muted); display:flex; flex-direction:column; gap:3px; }
.filters label { max-width:100%; }
select { max-width:100%; padding:6px 8px; border:1px solid var(--line); border-radius:6px; background:var(--card); color:var(--fg); font:inherit; }
.tablewrap { overflow-x:auto; border:1px solid var(--line); border-radius:8px; background:var(--card); }
table { border-collapse:collapse; width:100%; font-size:14px; }
th, td { text-align:left; vertical-align:top; padding:8px 10px; border-bottom:1px solid var(--line); }
th { position:sticky; top:0; background:var(--card); font-weight:600; }
td.small { font-size:13px; color:var(--muted); }
.pill { display:inline-block; padding:1px 8px; border-radius:10px; border:1px solid var(--line); font-size:12px; white-space:nowrap; }
footer.site { border-top:1px solid var(--line); color:var(--muted); font-size:14px; }
footer.site .in { padding-top:16px; padding-bottom:24px; }
"""


def page(title: str, body: str, *, noindex: bool = False, description: str = "") -> str:
    robots = '<meta name="robots" content="noindex">' if noindex else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title><meta name="description" content="{html.escape(description)}">{robots}
<link rel="stylesheet" href="/style.css"></head>
<body>
<header class="site"><div class="in"><a class="brand" href="/">AI in Australian Courts</a>
<nav><a href="/tracker.html">Tracker</a><a href="/rules.html">Court rules</a><a href="/checklist.html">Checklist</a><a href="/citecheck/">CiteCheck</a><a href="/about.html">About</a></nav></div></header>
<main>{body}</main>
<footer class="site"><div class="in">Not legal advice and not an official record: always check the official source.
Data CC BY 4.0, building on Damien Charlotin's AI Hallucination Cases database (CC BY 4.0).
<a href="/about.html#corrections">Corrections and takedown</a>. {html.escape(AUTHOR)}.</div></footer>
</body></html>
"""


def esc(x) -> str:
    return html.escape("" if pd.isna(x) else str(x))


def main() -> None:
    SITE.mkdir(exist_ok=True)
    (SITE / "downloads").mkdir(exist_ok=True)
    tracker = pd.read_csv(ROOT / "data/tracker.csv", dtype=str, keep_default_na=False)
    rules = pd.read_csv(ROOT / "data/rules.csv", dtype=str, keep_default_na=False)
    stats = json.loads((ROOT / "data/stats.json").read_text())
    shutil.copy(ROOT / "data/tracker.csv", SITE / "downloads/tracker.csv")
    shutil.copy(ROOT / "data/rules.csv", SITE / "downloads/rules.csv")
    (SITE / "style.css").write_text(CSS)

    # Tracker data for the page: public columns only, names withheld where the privacy rules say so.
    pub = []
    for _, r in tracker.iterrows():
        srl = r.party_type == "self_represented" or (not r.party_type and r.charlotin_party_type == "Pro Se Litigant")
        title = r.title_as_published if (SHOW_SRL_TITLES or not srl) else ""
        pub.append({k: r[k] for k in ["id", "mnc", "court", "court_level", "date", "party_type", "ai_use",
                                      "error_types", "consequence", "regulator_referred", "impugned_citations",
                                      "pinpoints", "verification_status", "details_withheld",
                                      "charlotin_party_type", "charlotin_outcome", "official_url"]} | {"title": title,
                                                                              "year": r.date[:4]})
    (SITE / "downloads/tracker.json").write_text(json.dumps(pub, ensure_ascii=False))

    n_rows = len(tracker)
    n_pub = stats["rows_publishing_extracted_fields"]
    n_held = stats.get("rows_with_details_withheld_pending_austlii", 0)
    n_rules = int(((rules.instrument != "") & (rules.instrument != "No specific AI guidance found")).sum())
    by_status = stats["by_verification_status"]
    index = f"""
<h1>AI in Australian Courts</h1>
<p class="lede">Open data on generative AI in Australian litigation: a tracker of decisions where AI-generated false or
inaccurate citations reached a court or tribunal, a matrix of court rules on AI, and a one-page checklist for checking
citations before filing.</p>
<div class="banner">Release 1, built from {n_rows} Australian decisions in Charlotin's database. Each row says how it was
checked; rows not yet checked show only facts read from the judgment and Charlotin's own coding.</div>
<div class="cards">
  <div class="card"><div class="num">{n_rows}</div><div>Australian decisions tracked</div>
    <div class="muted">{n_pub} with full details so far; details for {n_held} more are held back while a source-licensing question is resolved (<a href="/about.html#sources">why</a>)</div><a href="/tracker.html">Open the tracker</a></div>
  <div class="card"><div class="num">{n_rules}</div><div>court AI instruments in the rules matrix</div>
    <div class="muted">every cell tied to a paragraph of the official text</div><a href="/rules.html">Open the matrix</a></div>
  <div class="card"><div class="num">1</div><div>page: a verification checklist for paralegals</div>
    <div class="muted">HTML and A4 PDF</div><a href="/checklist.html">Open the checklist</a></div>
</div>
<h2>Download the data</h2>
<p><a href="/downloads/tracker.csv">tracker.csv</a> · <a href="/downloads/rules.csv">rules.csv</a> (CC BY 4.0). Verification
status of the {n_rows} rows: {", ".join(f"{esc(k).replace('_', ' ')} {v}" for k, v in by_status.items())}.</p>
"""
    (SITE / "index.html").write_text(page("AI in Australian Courts", index,
                                          description="Open data on generative AI errors in Australian courts, court AI rules and a citation checklist."))

    courts = sorted({p["court"] for p in pub if p["court"]})
    years = sorted({p["year"] for p in pub if p["year"]})
    tracker_body = f"""
<h1>Tracker</h1>
<p class="lede">Australian decisions in which AI-generated false or inaccurate material reached a court or tribunal.
Filter by court, year, party type or consequence. There is deliberately no name search.</p>
<div class="filters">
  <label>Court<select id="f-court"><option value="">All</option>{"".join(f"<option>{esc(c)}</option>" for c in courts)}</select></label>
  <label>Year<select id="f-year"><option value="">All</option>{"".join(f"<option>{esc(y)}</option>" for y in years)}</select></label>
  <label>Party type<select id="f-party"><option value="">All</option><option value="lawyer">Lawyer</option><option value="self_represented">Self-represented</option><option value="expert">Expert</option><option value="other">Other</option></select></label>
  <label>Consequence<select id="f-cons"><option value="">All</option><option>personal_costs_order</option><option>adverse_costs_order</option><option>regulator_referral</option><option>submissions_disregarded</option><option>warning_or_admonishment</option><option>application_or_appeal_dismissed</option><option>leave_refused</option><option>no_consequence_stated</option></select></label>
  <label>Checked<select id="f-status"><option value="">All</option><option value="luc_spot_checked">Spot-checked by Luc</option><option value="auto_verified">Auto-verified</option><option value="flagged_for_review">Awaiting review</option><option value="not_auto_verifiable">Not yet verified</option><option value="no_public_source">No public source</option></select></label>
</div>
<p class="muted" id="count"></p>
<div class="tablewrap"><table><thead><tr><th>ID</th><th>Decision</th><th>Court</th><th>Date</th><th>Party</th><th>Error types</th><th>Consequence</th><th>Checked</th></tr></thead><tbody id="rows"></tbody></table></div>
<p class="muted">Self-represented parties' case titles are withheld here; each decision's medium neutral citation identifies
it on the court's or publisher's site. "Auto-verified": every value rests on a quote found in the judgment text at the stated
paragraph; it has not been reviewed by a person. <a href="/about.html#method">How rows are checked</a>.</p>
<script>
const PARTY = {{"Pro Se Litigant":"self_represented","Lawyer":"lawyer","Expert":"expert","Judge":"other"}};
const LABEL = {{luc_spot_checked:"Spot-checked", auto_verified:"Auto-verified", flagged_for_review:"Awaiting review",
  not_auto_verifiable:"Not yet verified", no_public_source:"No public source"}};
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}}[c]));
let data = [];
fetch("/downloads/tracker.json").then(r => r.json()).then(d => {{ data = d; draw(); }});
document.querySelectorAll("select").forEach(s => s.onchange = draw);
function draw() {{
  const v = id => document.getElementById(id).value;
  const rows = data.filter(r => (!v("f-court") || r.court === v("f-court")) && (!v("f-year") || r.year === v("f-year"))
    && (!v("f-party") || (r.party_type || PARTY[r.charlotin_party_type] || "") === v("f-party"))
    && (!v("f-cons") || (r.consequence || "").split("; ").includes(v("f-cons")))
    && (!v("f-status") || r.verification_status === v("f-status")));
  document.getElementById("count").textContent = rows.length + " of " + data.length + " decisions";
  document.getElementById("rows").innerHTML = rows.map(r => `<tr>
    <td>${{esc(r.id)}}</td>
    <td>${{r.title ? esc(r.title) + "<br>" : ""}}<span class="small">${{esc(r.mnc)}}</span>${{r.pinpoints ? `<br><span class="small">at ${{esc(r.pinpoints)}}</span>` : ""}}</td>
    <td class="small">${{esc(r.court)}}</td><td class="small">${{esc(r.date)}}</td>
    <td>${{esc((r.party_type || "").replace("_", " ")) || `<span class="small">${{esc(r.charlotin_party_type)}} (Charlotin)</span>`}}</td>
    <td class="small">${{esc((r.error_types || "").replaceAll("_", " "))}}</td>
    <td class="small">${{esc((r.consequence || "").replaceAll("_", " ")) || (r.charlotin_outcome ? esc(r.charlotin_outcome) + " (Charlotin)" : "")}}</td>
    <td><span class="pill">${{r.details_withheld ? (r.impugned_citations ? "Details held back; fake citations checked by Luc" : "Details held back") : (LABEL[r.verification_status] || esc(r.verification_status))}}</span></td></tr>`).join("");
}}
</script>
"""
    (SITE / "tracker.html").write_text(page("Tracker: AI in Australian Courts", tracker_body, noindex=True,
                                            description="Australian decisions involving AI-generated false citations."))

    rows_html = ""
    for _, r in rules.iterrows():
        if r.instrument:
            rows_html += (f"<tr><td><strong>{esc(r.court)}</strong><br><span class='small'>{esc(r.instrument)}</span>"
                          f"<br><a href='{esc(r.url)}'>Official text</a> · <span class='small'>issued {esc(r.issued)}</span></td>"
                          f"<td>{esc(r.who_is_bound)}</td><td>{esc(r.disclosure_duty)}</td>"
                          f"<td>{esc(r.banned_or_cautioned_uses)}</td><td>{esc(r.verification_duty)}</td>"
                          f"<td>{esc(r.consequences)}</td><td class='small'>{esc(r.paragraph_refs)}</td></tr>")
        else:
            rows_html += (f"<tr><td><strong>{esc(r.court)}</strong></td><td colspan='6' class='small'>"
                          f"Instrument still to be collected by hand (as at {esc(r.as_at)}).</td></tr>")
    rules_body = f"""
<h1>Court rules on generative AI</h1>
<p class="lede">What each court's practice note or direction requires. Each cell is a plain-English summary, and the
paragraph references point to the official text. Every summary is backed by a quote that a script checks sits in the cited
paragraph. Rules as at {esc(rules.as_at.iloc[0])}.</p>
<div class="tablewrap"><table><thead><tr><th>Court and instrument</th><th>Who is bound</th><th>Disclosure</th>
<th>Banned or cautioned uses</th><th>Verification</th><th>Consequences</th><th>Paragraphs</th></tr></thead>
<tbody>{rows_html}</tbody></table></div>
<p class="muted">Instruments are labelled by jurisdiction: Victoria's SC Gen 23 (recordings of hearings) is a different
note from NSW's SC Gen 23 (generative AI). <a href="/downloads/rules.csv">Download rules.csv</a>.</p>
"""
    (SITE / "rules.html").write_text(page("Court AI Rules", rules_body,
                                          description="Australian court and tribunal practice notes on generative AI, by paragraph."))

    about = f"""
<h1>About</h1>
<h2 id="method">How the tracker is built and checked</h2>
<p>The starting point is the Australian rows of Damien Charlotin's AI Hallucination Cases database. Each judgment's text is
extracted locally, with publisher headers and footers removed. Claude (Anthropic) is asked to quote the passages on the AI error,
the impugned citations, consequences, referrals and practice notes cited, and every quote is then checked by script against the
judgment text, character for character, with its paragraph number. A second step proposes field values from those verified quotes
only, and any value without a supporting quote is discarded.</p>
<p>Every row then goes through automatic checks: the citation matches the judgment's header, titles and impugned citations are copied
exactly, characterisations have textual support, paragraph counts match the court's own certificate, and the row is compared with
Charlotin's coding. These checks prove that each value rests on real text at the stated paragraph. They cannot prove the text was
read correctly, so rows that pass are labelled <em>auto-verified</em>. A random sample of 10 rows, fixed before any extraction, was
checked by hand against the official judgment and labelled <em>spot-checked</em>. Rows the checks flag are labelled <em>awaiting
review</em> until a person has read them.</p>
<h2 id="sources">Sources and a pending question</h2>
<p>Most judgment copies in Charlotin's database were printed from AustLII. Our code never accessed AustLII, but the text of those copies
(with AustLII's headers removed) was processed by the AI model. We are asking AustLII whether this use is acceptable. Until it replies,
the details the AI extracted from those copies are held back. Rows checked by hand against the judgment, facts read by script (citation,
court, date) and Charlotin's own coding are shown, as are the fake citations Luc read against the judgment in 20 of the held-back rows.</p>
<h2>Contributions and AI use</h2>
<p>This project was built with Claude Code (Anthropic), an AI coding assistant, and this is disclosed in full. Claude wrote the
pipeline, the site (including CiteCheck AU) and first drafts of the rules summaries and checklist, and Claude models perform the
first-pass extraction. Luc Taya designed the project, made the judgement calls recorded in the repository's decisions log, checked
the random spot-check sample and the fake citations in 20 held-back rows against the judgments, checked the rules matrix and edited
the checklist. No figure is typed by hand: each is produced by a committed script
from the data.</p>
<h2>Privacy</h2>
<p>The tracker records only what each judgment says. Self-represented parties can be filtered but not searched by name, and their case
titles are not shown on the tracker page. Family law matters use only the court's anonymised title (Family Law Act 1975 (Cth) s 114Q).</p>
<h2 id="corrections">Corrections and takedown</h2>
<p>Email <a href="mailto:ai.courts.corrections@proton.me">ai.courts.corrections@proton.me</a>. Requests are answered within 7 days, and every change is logged in the changelog. If you are a self-represented party named in a decision, you can ask for identifying detail to be removed even where the entry is accurate.</p>
<h2>Licence and credits</h2>
<p>Data CC BY 4.0. Built on Damien Charlotin's AI Hallucination Cases database (CC BY 4.0). Court instruments are linked to their
official sources.</p>
<p>{html.escape(AUTHOR)}.</p>
"""
    (SITE / "about.html").write_text(page("About: AI in Australian Courts", about,
                                          description="Method, AI use, privacy and corrections."))

    # Downloads hold court-published titles: keep them out of search indexes (PRIVACY.md rule 2).
    # CiteCheck's index files (built into site/citecheck/ by Vite; D038) hold case metadata: no indexing.
    (SITE / "robots.txt").write_text("User-agent: *\nDisallow: /data/\nDisallow: /downloads/\nDisallow: /citecheck/data/\n")
    (SITE / "_headers").write_text("/data/*\n  X-Robots-Tag: noindex\n/downloads/*\n  X-Robots-Tag: noindex\n"
                                   "/citecheck/data/*\n  X-Robots-Tag: noindex\n"
                                   "/tracker.html\n  X-Robots-Tag: noindex\n"
                                   "/tracker\n  X-Robots-Tag: noindex\n")  # Pages serves /tracker.html at /tracker
    print(f"site built: {n_rows} tracker rows ({n_pub} with extracted fields), {n_rules} instruments")


if __name__ == "__main__":
    main()
