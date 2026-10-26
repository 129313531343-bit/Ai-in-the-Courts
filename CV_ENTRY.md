# CV entry: AI in Australian Courts (Release 1)

Hand-off for Luc's CVs. Every number below comes from the project's data (`data/stats.json`, `data/rules.csv`, `data/interim/agreement.json` and the methods note) as at 26 October 2026. Re-check them against the live site before reuse if the data has been updated.

## (a) CV bullets

**AI in Australian Courts**: independent legal-data project, October 2026 · [ai-in-australian-courts.pages.dev](https://ai-in-australian-courts.pages.dev)

### Economics / finance version
- Built a reproducible Python pipeline that assembles a dataset of 112 Australian decisions in which AI-generated false citations reached a court or tribunal, drawn from an open international database and the judgments themselves. Every published figure is produced by a committed script.
- Measured data quality before publishing:
  - a pre-registered random audit of 10 rows found 91.1% of judgement-based fields correct (72 of 79; Wilson 95% CI 82.8–95.6%);
  - party coding agreed with the source database in 90.7% of 97 rows (Cohen's kappa 0.74).
- Ran the AI extraction for US$9.88 under a self-imposed US$30 cap. All 1,615 extracted quotations were matched character for character against the judgment text.

### Legal version
- Built a public tracker of 112 Australian decisions in which AI-generated false citations reached a court or tribunal.
- Compiled a matrix of 14 AI practice notes, practice directions and guidance notes across 13 Australian courts and tribunals, including the Federal Court, the Supreme Courts of NSW, Victoria, Queensland and Western Australia, and the Fair Work Commission.
  - It sets out who is bound, disclosure and verification duties, banned or cautioned uses, and consequences.
  - Each summary is tied to verbatim quotations (233 in total), each checked against the paragraph it cites.
- Wrote a one-page citation-verification checklist for paralegals (web page and A4 PDF), citing the matrix paragraphs. In the source database's coding, about half of the Australian cases with coded errors (55 of 108) involved misrepresented authorities or false quotes, not only invented cases.

### General / AI version
- Designed and shipped an AI-assisted legal-data pipeline (Python; Claude API with citations and structured outputs) that extracts facts from 104 court judgments. Every extracted field must rest on a quotation found verbatim in the judgment; all 1,615 quotations matched.
- Automatically checked every row and ran a pre-registered human audit (91.1% of judgement fields correct; 95% CI 82.8–95.6%).
- Published a static site, open data (CC BY 4.0), a two-page methods note and a public log of every judgement call.

### Release 2 preview bullet (optional; keep the word "preview" until the evaluation is published)
- Built CiteCheck AU (preview), an in-browser tool that finds the case and statute citations in a document and checks each against 187,443 Australian decisions, 63,282 law-report citations and 13,747 Commonwealth Acts. Party names are stored only as one-way fingerprints, and documents never leave the browser. Its evaluation on a frozen held-out test set is in progress.

## (b) Cover-letter sentence

I built AI in Australian Courts (ai-in-australian-courts.pages.dev), a public tracker of 112 Australian decisions in which AI-generated false citations reached a court, together with a matrix of 14 court AI practice notes and a one-page verification checklist, so that every summary and figure can be traced back to its source.

## (c) Public URLs

- Site: https://ai-in-australian-courts.pages.dev
- Tracker: https://ai-in-australian-courts.pages.dev/tracker
- Rules matrix: https://ai-in-australian-courts.pages.dev/rules
- Checklist (web): https://ai-in-australian-courts.pages.dev/checklist
- Checklist (A4 PDF): https://ai-in-australian-courts.pages.dev/checklist.pdf
- Code, data and decision log: https://github.com/129313531343-bit/Ai-in-the-Courts
- Methods note (PDF): https://github.com/129313531343-bit/Ai-in-the-Courts/blob/main/docs/methods.pdf
- CiteCheck AU (preview): https://ai-in-australian-courts.pages.dev/citecheck/

## (d) Status

**Live since:** 26 October 2026 (site deployed on Cloudflare Pages).

**Still in progress:**
- **AustLII permission:** most judgment copies are AustLII printouts, and we have asked AustLII whether AI processing of them fits its terms. Until it replies, AI-extracted details for 55 decisions are held back. 12 decisions publish full details. Every decision shows its date, and 105 of 112 also show their citation and court (DECISIONS.md D007, D024).
- **Rows awaiting review:** 37 rows are flagged by the automatic checks for human review.
- **Two "no guidance found" entries:** the District Court of Western Australia and the State Administrative Tribunal (WA) were searched by script, but not yet confirmed by hand.
- **Corrections to the source database:** five court-label corrections are drafted for its maintainer, but not yet sent.
- **Release 2:** CiteCheck AU has been online as a preview since 26 October 2026, labelled "not yet evaluated". Before its accuracy is published, the evaluation set must be completed and frozen (statute items, 30 adversarial items, inspection), then run once on the held-out split. A practice note is still to be written.
