# Changelog

All changes to published data (tracker.csv, rules.csv) and the site are logged here, newest first.

## Unreleased
- 2026-10-25: Project started. Downloaded Charlotin CSV (2,208 rows; 112 Australian) and filtered to Australia.
- 2026-10-25: Downloaded the 105 judgments Charlotin hosts for Australian rows (SHA-256 manifest committed; files not committed). Read each judgment's own MNC (103 of 105), court level, page count and provenance (78 AustLII prints, 1 Wikisource export). The rows are 2,208 in today's download, against 2,207 noted in the brief on 23 Oct; the Australian rows are unchanged at 112.
- 2026-10-25: Pass A (Claude Opus 5.5, Message Batches) run on the 104 judgments with a text layer: 1,615 quotes, all found at exact character offsets in the locally extracted text. Pass B run (field proposals from verified quotes only). Automatic row verification added (D016). Rules matrix drafted for 7 instruments (NSW, Vic x2, Qld x3, WA), with all 75 supporting quotes verified in the cited paragraphs of the official texts. Draft checklist and static site built.
- 2026-10-25: Automatic verification of all rows: 65 auto-verified, 39 flagged for Luc, 4 not auto-verifiable, 4 with no public source. Party type agrees with Charlotin in 90.7% of 97 rows (Cohen's kappa 0.743). Total API spend US$9.88 of the US$30 cap.
