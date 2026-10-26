# AI in Australian Courts

Open data and tools on generative AI in Australian litigation:

1. **Tracker**: Australian decisions in which AI-generated false or inaccurate citations reached a court or tribunal.
2. **Rules matrix**: what each court and tribunal's AI practice notes and guidelines require.
3. **Verification checklist**: a one-page checklist for paralegals, citing only paragraphs in the matrix.
4. **CiteCheck AU** (Release 2, preview): an in-browser tool that finds the case and statute citations in a document and checks each against an open snapshot of Australian law (`citecheck/`).

Status: Release 1 live since 26 October 2026 at https://ai-in-australian-courts.pages.dev. Release 2 in progress: CiteCheck AU is online as a preview whose accuracy has not yet been measured; its evaluation set is being frozen first. Nothing here is legal advice. The data are not an official record; always check the official source.

## Data

| File | What it is | Licence |
|---|---|---|
| `raw/SHA256SUMS.txt` | SHA-256 hashes of Damien Charlotin's AI Hallucination Cases CSV as downloaded, and its Australian rows. The files themselves are not in this repo because they name self-represented litigants (see PRIVACY.md). `scripts/00_download_charlotin.py` downloads the current version and reports whether it matches the Release 1 snapshot. | CC BY 4.0 (Charlotin) |
| `data/tracker.csv` | The tracker (Release 1). Case titles are withheld for self-represented parties. | CC BY 4.0 |
| `data/rules.csv` | The rules matrix (Release 1) | CC BY 4.0 |

The tracker builds on Charlotin's database (https://www.damiencharlotin.com/hallucinations/), used under CC BY 4.0. Each row's `verification_status` says how far its fields were checked: `luc_spot_checked` (read against the judgment by Luc), `auto_verified` (passed every automatic check, not read by a person), `flagged_for_review`, `not_auto_verifiable` or `no_public_source`. Fields extracted by AI from AustLII-printed copies are held back until AustLII answers a licensing question (DECISIONS.md D007, D024); `details_withheld` marks those rows.

CiteCheck AU's indexes are built from the Open Australian Legal Corpus v7.1.0 by Isaacus (CC BY 4.0; current to 10 March 2025) and the Federal Register of Legislation (CC BY 4.0). They are built locally and deployed with the site, never committed; their SHA-256 checksums are in `data/interim/citecheck_index_manifest.csv`. Party names are published only as one-way fingerprints (DECISIONS.md D031, D033). The evaluation items are in `eval/` (citation strings, labels and source citations only).

Judgment text is never committed. Downloaded judgments are cached locally, and only their SHA-256 hashes are published (`data/interim/doc_manifest.csv`).

## Privacy, corrections and takedown

The tracker records only what each judgment says. Self-represented parties can be filtered by court, year, party type and consequence, but cannot be searched by name. Family law matters use only the court's anonymised title. Corrections and takedown requests: see [CORRECTIONS.md](CORRECTIONS.md). All changes are logged in [CHANGELOG.md](CHANGELOG.md).

## Reproducing

```bash
python3 -m venv ~/.venvs/ai-in-courts   # outside this folder: its path contains ':'
~/.venvs/ai-in-courts/bin/pip install -r requirements.txt
PY=~/.venvs/ai-in-courts/bin/python
$PY scripts/00_download_charlotin.py 2026-10-25   # Charlotin's CSV into raw/ (checks the published hash)
$PY scripts/01_filter_charlotin.py         # Australian rows; proposed court from name/filename/label
$PY scripts/02_download_docs.py            # Charlotin-hosted judgments, 1 request / 5 s, SHA-256 manifest
$PY scripts/03_doc_metadata.py             # own MNC, court, pages, scanned?, provenance, paragraph numbering
$PY scripts/04_pass_a.py estimate          # Pass A: quotes with citations ('submit' needs ANTHROPIC_API_KEY in .env)
$PY scripts/05_verify_quotes.py            # every quote checked byte-for-byte against the judgment text
$PY scripts/06_pass_b.py estimate          # Pass B: field proposals from verified quotes only
$PY scripts/07_spot_check_sample.py        # pre-registered random spot-check sample (run once, before extraction)
$PY scripts/09_public_manifests.py         # name-free hash manifests published instead of name-bearing files
$PY scripts/08_verify_rows.py              # automatic checks on every row; Luc's review queue
$PY scripts/10_fetch_rules.py              # official AI practice notes and directions (robots-checked, 1 request / 5 s)
$PY scripts/11_build_rules.py              # rules.csv; every cited paragraph checked against the official text
$PY scripts/12_build_tracker.py            # tracker.csv and stats.json
$PY scripts/13_review_server.py            # local review page at http://127.0.0.1:8765
$PY scripts/14_build_checklist.py          # checklist HTML and one-page A4 PDF
$PY scripts/15_build_site.py               # static site in site/
$PY scripts/17_build_docs.py               # methods paper (docs/methods.pdf) and private fact pack
$PY -m pytest                              # unit tests
```

Release 2 (CiteCheck AU) adds, after downloading the corpus to `cache/corpus/corpus.jsonl` (DECISIONS.md D029 gives the pinned revision and SHA-256):

```bash
$PY scripts/20_export_tables.py            # court table for the TypeScript parser
$PY scripts/21_corpus_scan.py              # corpus metadata only (no text kept); court-year ranges and gap rates
$PY scripts/22_reserve_eval.py             # 2% of judgments reserved as evaluation sources (seed 20261026)
$PY scripts/23_build_index_a.py            # index (a): neutral citations, with party fingerprints
$PY scripts/24_build_index_c.py            # index (c): Acts in force at the snapshot
node citecheck/scripts/mine_reports.ts     # report citations mined with the shipped parser (eval sources excluded)
$PY scripts/25_build_index_b.py            # index (b): reports cited by 2+ judgments
$PY scripts/29_fetch_cth_acts.py           # index (d): Commonwealth Acts with former names (1 request / 10 s)
$PY scripts/26_index_manifest.py           # checksums; 10 MB budget check
$PY scripts/27_build_eval.py               # evaluation case items (real + synthetic from aic/corrupt.py)
$PY scripts/28_build_fabricated.py         # evaluation items from the fake citations Luc checked
cd citecheck && npm ci && npm test && npm run build   # parser and matcher tests; site into site/citecheck/
```

npm's usual `npx` lookup breaks when a folder path contains ':' (this one does), so the package scripts call `node` directly.

Judgment files are cached in `cache/` and never committed. Anthropic API keys live only in a gitignored `.env`.

## Contributions and AI use

This project was built with Claude Code (Anthropic), an AI coding assistant, and that use is disclosed here in full.

- **Built by Claude (AI), directed and reviewed by Luc Taya:** the data pipeline scripts, the review page, the site code, CiteCheck AU (parser, matcher, index builds and page), and first drafts of the rules matrix cells and the checklist. The first-pass extraction of fields from judgments uses Claude models through the Anthropic API. Every such field records the verbatim quote it rests on.
- **Done by Luc Taya:** the project design and scope; deciding each judgement call in [DECISIONS.md](DECISIONS.md) (many are first proposed by Claude, and each entry shows whether Luc has approved it); spot-checking 10 pre-registered random tracker rows against the official judgments (marked `luc_spot_checked`; rows that pass every automatic check but were not reviewed by Luc are marked `auto_verified`); reading the fake citations in 20 further rows against the judgments (DECISIONS.md D034, D035); checking the rules matrix against the official instruments; editing the checklist; and approving each release.
- No figure in any output is typed by hand. Each is produced by a committed script from the data.

## About

Luc Taya, Economics (Honours) graduate, University of Western Australia.
