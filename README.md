# AI in Australian Courts

Open data and tools on generative AI in Australian litigation:

1. **Tracker**: Australian decisions in which AI-generated false or inaccurate citations reached a court or tribunal.
2. **Rules matrix**: what each court and tribunal's AI practice notes and guidelines require.
3. **Verification checklist**: a one-page checklist for paralegals, citing only paragraphs in the matrix.

Status: Release 1 in progress (started 25 October 2026). Nothing here is legal advice. The data are not an official record; always check the official source.

## Data

| File | What it is | Licence |
|---|---|---|
| `raw/SHA256SUMS.txt` | SHA-256 hashes of Damien Charlotin's AI Hallucination Cases CSV as downloaded, and its Australian rows. The files themselves are not in this repo because they name self-represented litigants (see PRIVACY.md). `scripts/00_download_charlotin.py` downloads the current version and reports whether it matches the Release 1 snapshot. | CC BY 4.0 (Charlotin) |
| `data/tracker.csv` | The tracker (Release 1). Case titles are withheld for self-represented parties. | CC BY 4.0 |
| `data/rules.csv` | The rules matrix (Release 1) | CC BY 4.0 |

The tracker builds on Charlotin's database (https://www.damiencharlotin.com/hallucinations/), used under CC BY 4.0. Each row records whether its fields were checked against the judgment (`luc_verified`) or rest on Charlotin's coding alone (`charlotin_coding_not_independently_verified`).

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

Judgment files are cached in `cache/` and never committed. Anthropic API keys live only in a gitignored `.env`.

## Contributions and AI use

This project was built with Claude Code (Anthropic), an AI coding assistant, and that use is disclosed here in full.

- **Built by Claude (AI), directed and reviewed by Luc Taya:** the data pipeline scripts, the review page, the site code, and first drafts of the rules matrix cells and the checklist. The first-pass extraction of fields from judgments uses Claude models through the Anthropic API. Every such field records the verbatim quote it rests on.
- **Done by Luc Taya:** the project design and scope; deciding each judgement call in [DECISIONS.md](DECISIONS.md) (many are first proposed by Claude, and each entry shows whether Luc has approved it); spot-checking 10 pre-registered random tracker rows and every automatically flagged row against the official judgments (marked `luc_spot_checked`; rows that pass every automatic check but were not reviewed by Luc are marked `auto_verified`); checking the rules matrix against the official instruments; editing the checklist; and approving each release.
- No figure in any output is typed by hand. Each is produced by a committed script from the data.

## About

Luc Taya, Economics (Honours) graduate, University of Western Australia.
