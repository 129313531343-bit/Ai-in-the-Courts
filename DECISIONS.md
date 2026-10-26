# Decisions log

Every judgement call, with the options considered. **Status: proposed** means Claude made the call provisionally and it awaits Luc's sign-off. **Status: Luc** means Luc decided or approved it.

---

### D001: Python version and venv location (25 Oct 2026)
- **Context:** The brief asks for Python 3.12. This Mac has only Python 3.14.4 and no Homebrew. Python refuses to create a venv inside this folder because its path contains `:`, the PATH separator.
- **Options:** (a) install 3.12 from python.org; (b) use 3.14 with the venv at `~/.venvs/ai-in-courts`; (c) rename the project folder.
- **Chosen:** (b). pandas, pydantic, rapidfuzz, pdfplumber and anthropic all install and import on 3.14. CI will pin 3.12, so anything that only works on 3.14 would show up there. `pyproject.toml` declares `>=3.12`.
- **Status:** proposed.

### D002: Court normalisation (25 Oct 2026)
- **Context:** Charlotin's `Court` column has 58 distinct labels for 112 Australian rows, and some are wrong (e.g. a FedCFamC2G decision labelled "Federal Court"; three general federal law decisions labelled "Family Court").
- **Options:** (a) map the labels only; (b) take the court from the decision's own medium neutral citation (MNC); (c) wait for the AI extraction.
- **Chosen:** (b), in two steps. `01_filter_charlotin.py` proposes a court from an MNC in Charlotin's case name, filename or AustLII URL text, falling back to a map of unambiguous labels. `03_doc_metadata.py` then reads the MNC printed on the judgment itself (first 3 pages; the first known-court MNC whose year matches the decision year). This found the judgment's own MNC in 103 of 105 documents; the 2 misses are a scanned PDF and a .docx. Charlotin's original column is kept unchanged.
- **Why not (c):** a regex on the judgment's own header is deterministic and auditable; nothing about it needs a model.

### D003: Court levels (25 Oct 2026)
- **Options:** (a) superior / not superior; (b) apex / superior / intermediate / lower / tribunal / other.
- **Chosen:** (b), in `data/reference/court_codes.csv`. The resulting counts are 35 superior, 21 intermediate, 44 tribunal and 5 other, across 105 documents.
- **To confirm (Luc):** the status of FedCFamC Division 2 (currently "intermediate") and the NSW LEC (currently "superior"). These change how many rows are in the "every superior-court row" review set.
- **Status:** Luc (approved 26 Oct 2026).

### D004: What counts as "no public source" (25 Oct 2026)
- **Chosen:** a row has no public source only if no free, readable text of the judgment is linked. AustLII and NSW Caselaw links count as public: a person can read them, though our code never fetches them. The 2 Westlaw-only SA rows, the PerthNow row and the blog row are `no_public_source` unless Luc finds the judgment by hand.

### D005: What code may fetch (25 Oct 2026)
- **Charlotin's site:** its robots.txt allows `User-agent: *` and sets `Content-Signal: search=yes, ai-train=no, use=reference`. It sets no `ai-input` signal, which under its own preamble neither grants nor restricts that use. It also disallows named AI crawlers (including ClaudeBot and anthropic-ai). Our downloader is not a crawler. It is a one-off, user-run script that fetches only the 105 `/documents/` judgments, at 1 request every 5 s, with an honest user-agent. Nothing is used for training.
- **Never fetched in code:** AustLII (blocks bots; reserves AI uses) and NSW Caselaw (its terms exclude robots). The NSW Caselaw row and the 2 AustLII-only rows are left for Luc to read by hand. MNCs are read from AustLII *URL text* only.

### D006: Private planning files (25 Oct 2026)
- Anything about Luc's plans after Perth lives in `private/` (gitignored). Public text describes Luc only as "Economics (Honours) graduate, University of Western Australia".

### D007: What Pass A sends to the API (25 Oct 2026)
- **Finding:** 78+ of Charlotin's 105 copies are AustLII printouts (URL footers, page-1 banner or "Australasian Legal Information Institute" banner), and 1 is a Wikisource export. We never fetch AustLII, but the brief notes AustLII reserves AI uses.
- **Options:** (a) send Charlotin's PDFs as-is; (b) send locally extracted text with page and publisher furniture stripped; (c) use official court copies only (about 2–3 h of Luc's time).
- **Chosen by Luc: (b)**, on condition that Luc reads AustLII's terms himself first. **25 Oct 2026: Luc reported that he had read AustLII's terms and approved sending the AustLII-print judgments (as stripped text).** His reasons are to be added here in his own words.
- **How (b) works:** `aic/doctext.py` strips running headers and footers, page numbers, AustLII's banner and page-1 header block (database name, title line, "Last Updated"), AustLII URL footers, and Wikisource cover and end pages. It also de-duplicates characters printed twice to fake bold. The text is cached per row (`aic/corpus.py`, keyed by source SHA-256 and `EXTRACTION_VERSION`), and its SHA-256 is recorded when sent. Citations come back as character offsets into exactly that text, so each quote is checked byte-for-byte and mapped to page and paragraph. Library versions are pinned in `requirements.txt` so the extraction is reproducible.
- `official_url` in the tracker is always the court's or an official publisher's URL. It is never Charlotin's copy, an AustLII print or Wikisource.
- **26 Oct 2026, reopened:** asked for his reasons in his own words, Luc answered: "I am unsure if this is acceptable to do."
  - **What has already happened:** on 25 Oct 2026, after Luc's go-ahead, the stripped text of 104 judgments (94 of them AustLII prints) was sent to Anthropic's API (Message Batches) for extraction. That cannot be undone. Nothing has been published.
  - **Until this is resolved,** no field extracted by AI from an AustLII-print copy is published.
  - **Options:** (i) ask AustLII directly (Luc sends; draft provided) and act on the reply; (ii) rebuild those rows from the courts' own published copies, downloaded by Luc; (iii) withdraw the AI-extracted fields for AustLII-print rows and publish only facts read by script, Charlotin's coding and Luc's spot-check.
  - **Recommendation:** (i), because it settles the question at the source, with (iii) as the fallback if there is no answer by launch.
- **26 Oct 2026:** Luc chose option (i). He will email AustLII himself and report the reply. The fallback, if there is no answer by launch, is (iii).
- **26 Oct 2026:** Luc reported that he had sent the email to AustLII.
- **Status:** OPEN (awaiting AustLII's reply).

### D008: Pass A development sample (25 Oct 2026)
- **Options:** (a) 10 random documents; (b) a fixed, stratified 10.
- **Chosen:** (b) with seed 20261025: 4 lawyer rows, 4 self-represented rows, 1 other party (expert, judge or blank) and 1 .docx, so that both the PDF (page location) and plain-text (character location) citation paths are exercised. Scanned PDFs are excluded until OCR'd. The sample is written to `data/interim/pass_a/dev_sample.csv`.
- **Gate:** superseded by D009 (Opus 5.5 chosen) and D016 (automatic verification). The dev sample is kept as the only rows on which prompts may be tuned, and it is excluded from the random spot-check.
- **Status:** proposed.

### D009: Models and settings for Pass A and Pass B (25 Oct 2026)
- **Model: `claude-opus-5-5`, chosen by Luc on 25 Oct 2026**, replacing the brief's cost choice of Sonnet 5.5. The scripts default to Opus; `--model sonnet` remains available. Every estimate prints both prices.
- **Settings:** adaptive thinking, effort `high`, `max_tokens` 16000, Message Batches (50% price). No temperature, top_p or top_k: they return a 400 on API version 2026-10-21, which SDK 2.3.0 sends by default. The server-side `fallbacks` parameter is rejected on Batches, so a `refusal` stop reason is recorded and the row goes to hand review.
- **Spend:** exact input tokens come from the free count_tokens endpoint before each batch; anything over US$10 needs Luc's explicit yes.
- **Status:** Luc.

### D010: Quote check (25 Oct 2026)
- A Pass A quote passes if rapidfuzz `partial_ratio` ≥ 97 against the judgment text, after the same normalisation on both sides (`aic/textnorm.py`): NFKC including ligatures, quotes and dashes to ASCII, soft hyphens and zero-width characters removed, de-hyphenation across line breaks (only before a lower-case letter, so "Smith-Jones" survives), running headers and page numbers stripped (`aic/doctext.py`), and whitespace collapsed.
- The quote is looked for on the cited pages first (the API's page ranges are 1-indexed with an exclusive end page, per Anthropic's citations docs), then anywhere in the judgment. A quote found only elsewhere is marked `other_pages`.
- Failures go to hand review. Scanned PDFs are marked `needs_ocr`; ocrmypdf is not installed yet.

### D011: Paragraph numbers (25 Oct 2026)
- **Options:** (a) the nearest number at the start of a line; (b) candidates filtered by font size and left margin, keeping the longest run that counts up by one.
- **Chosen:** (b). Footnotes (smaller font), indented numbers and numbered orders ("1. The appeal is dismissed") are excluded. On a tie, the most recent "n−1" is linked, so the reasons' numbering wins over the orders'. Unit tests in `tests/test_doctext.py` cover these cases. 2 of 103 PDFs have incomplete numbering (flagged), and .docx files lose Word's automatic numbering. Every proposed paragraph is shown to Luc on the review page.

### D012: Pass B sees only verified quotes (25 Oct 2026)
- Pass B gets only the quotes that passed D010, as plain text with IDs. Any value whose quote IDs are empty or unknown is blanked by code (`aic/extract.py: enforce_quotes`), whatever the model returned.

### D013: Two additions to the brief's categories (25 Oct 2026)
- **`not_located`** as a sixth characterisation of an impugned citation, for courts that say only that a case "could not be found". Recording that as `non_existent` would overstate what the court said. It can be merged into `non_existent` for summary statistics if Luc prefers.
- **`ai_use`** (admitted / found_by_court / suspected / denied) as a new tracker field, so that a court's suspicion is never presented as an admission. This matters for fairness to the people named.
- **Status:** Luc (approved 26 Oct 2026).

### D014: Which fields unverified rows publish (25 Oct 2026)
- **Options:** (a) publish the model's proposed fields for every row, marked unverified; (b) for rows Luc has not verified, publish only the document-derived MNC, court, level and date, the official URL, and Charlotin's own coding (party type, outcome).
- **Recommendation:** (b). No model-extracted analytical field is published until Luc has checked it against the judgment.
- **Status:** Luc (approved 26 Oct 2026).

### D015: No-index on tracker pages (25 Oct 2026)
- In addition to the brief's rule (no names in the search index or page metadata), tracker row pages carry `noindex` and use neutral IDs (`AIC-0001`). This makes it harder to reach a self-represented person's entry by searching their name.
- **Status:** Luc (approved 26 Oct 2026).

### D016: Verification: automatic checks on every row, plus Luc's random spot-check (25 Oct 2026)
- **Change of plan (Luc):** instead of Luc checking all 22 lawyer rows and every superior-court row (about 10 h), every row is verified automatically and Luc reviews 10 random rows plus every flagged row.
- **Automatic checks** (`aic/verify.py`, run by `scripts/08_verify_rows.py`):
  - every value's quotes are found byte-for-byte in the judgment text, each with a paragraph number;
  - no unsupported value had to be dropped;
  - the MNC equals the one read by regex from the judgment header;
  - the title and each impugned citation are copied exactly;
  - each characterisation has a textual cue in its supporting quote;
  - error types are consistent;
  - family-law status agrees with the court code;
  - the paragraph count matches the court's own certificate ("the preceding eighty-four (84) numbered paragraphs");
  - party type and referral agree with Charlotin;
  - the copy is not a secondary (Wikisource) copy.
- **What this can and cannot show:** it proves that every value rests on real text at the stated paragraph. It cannot prove the model read that text correctly. So rows that pass are labelled `auto_verified`, not human-verified, and the accuracy of the readings is estimated from Luc's random spot-check (n = 10, reported with a Wilson 95% interval).
- **Spot-check sample:** pre-registered before any extraction (`scripts/07_spot_check_sample.py`, seed 20261031, 10 of 94 eligible rows, excluding the 10 dev-sample rows). Flagged rows are reviewed as well but are not used for the accuracy estimate, because they are not random.
- **verification_status values** (replacing the brief's list): `luc_spot_checked` / `auto_verified` / `flagged_for_review` (until Luc resolves it, then `luc_spot_checked`) / `not_auto_verifiable` / `no_public_source`. Only `luc_spot_checked` and `auto_verified` rows publish extracted analytical fields (D014).
- **"Official text" caveat:** the automatic checks compare against the copy we hold. For most rows that is an AustLII print of the court's judgment, not the authorised version. Automatically fetching official versions is not possible within the rules: the Federal Court site blocks bots, NSW Caselaw's terms exclude robots, and many tribunals publish only via AustLII. Luc's spot-check uses the official source.
- **Status:** Luc (plan; labels approved 26 Oct 2026).

### D017: Quotes above paragraph 1 are "front matter", not missing pinpoints (25 Oct 2026)
- Orders, catchwords and cover sheets sit above the first numbered paragraph. A consequence quoted from the orders ("The applicant's lawyer personally pay ... costs") is properly sourced but has no paragraph number. These quotes are labelled `front_matter`, and the tracker shows the pinpoint as "orders". Only quotes inside the numbered reasons that lack a paragraph number are flagged. Documents with no detectable numbering (e.g. a .docx whose Word numbering is not part of the text) are flagged for review.

### D018: Who says a citation is false (`asserted_by`) (25 Oct 2026)
- The dev sample showed a "misdescribed authority" that was only the respondent's contention, recorded by the court (row 1568). Pass B now records `asserted_by` (court / party / unclear) for each impugned citation, and any citation not impugned by the court itself is flagged for Luc. The tracker should present only the court's own characterisations as findings.
- **Status:** Luc (approved 26 Oct 2026).

### D019: Rules matrix built and checked the same way as the tracker (25 Oct 2026)
- Each cell is a plain-English summary (drafted by Claude) backed by short verbatim quotes with paragraph numbers (`data/reference/rules_evidence.csv`). `scripts/11_build_rules.py` checks that every quote occurs in the official text *inside the cited paragraph*. Paragraph spans are read from the instrument's own numbering, accepting only numbers that move forward and are in the instrument's style (decimal for Vic, whole numbers for NSW, Qld and WA). That rejects footnote numbers and headings such as WA's "9.21.". All 75 quotes are verified.
- **Brief corrections confirmed against the official texts:**
  - NSW SC Gen 23 is still the 28 Jan 2025 version (no 2026 revision found; the court invited submissions on it in Nov 2025).
  - The Vic SC Gen 25 paragraph numbers in the brief (6.7, 7.1, 7.4, 7.6) are right. The court's October 2026 file differs from May's only in a spacing fix and the signatory.
  - Vic SC Gen 26 (14 Sep 2026) has AI content at paras 8.7 and 8.12.
  - The Qld SC PD 5 of 2025 file is unchanged.
  - Qld District Court PD 12 and P&E Court PD 7 of 2025 are word-for-word identical to it, apart from the court name.
  - WA PD 9.21 was inserted on 10 Dec 2025 (the CPD amendment table).
- **Open question for Luc:** check every cell (the brief's 7 h), or spot-check like the tracker, since every cell is already tied to a verified quote?

### D020: No judgment excerpts in the public repo (25 Oct 2026)
- Pass A outputs (`data/interim/pass_a/<row>.json`), `quote_checks.csv` and `verification_checks.csv` contain verbatim passages of judgments (about 1,600 quotes), so they are gitignored, in line with the brief's rule never to commit judgment text. What is committed: document SHA-256 hashes, the sent-text hashes (`sent_text.csv`), Pass B field values with quote IDs, row statuses and the spend log. That is enough to audit the pipeline, and anyone holding the same judgment copies can regenerate the quotes. The tracker publishes only field values, impugned citations and pinpoints, not passages.

### D021: Tuning the automatic checks to remove false alarms (25 Oct 2026)
- **First full run:** 58 of 104 rows flagged. Inspection showed most flags were the checks being too strict, not extraction errors. All changes reduce false alarms on principle; none was made to let a particular row pass:
  - **Verifier bug:** pandas `itertuples()` renamed the `pass` column (a Python keyword), so every quote looked unverified. Fixed, with a regression test.
  - **"Non-existent case but no non-existent citation listed": dropped.** Courts often reproduce only some impugned citations and decline to reproduce fabricated ones.
  - **Characterisation cues widened** with ordinary judicial phrasing, after reading supporting quotes whose characterisations were correct: "is not about", "nor does … stand for", "could find such a case", "there is nothing in", "does not match the citation", "refers to a … case which has no relevance".
  - **Titles:** pass if found exactly, ignoring case, or with every word in order within a short span (cover pages separate the parties with role labels). No word may be missing, so nothing can be added.
  - **MNC comparison:** ignores leading zeros and missing brackets ("[2025] QIRC 046" = "[2025] QIRC 46"; "2025 ATMO 264" as printed).
  - **Blank party type:** not a disagreement with Charlotin; the tracker then shows Charlotin's coding.
  - **A dropped `family_law_matter`** is not a flag, because the court code decides family-law status.
- **Result:** 65 auto-verified, 39 flagged, 4 not auto-verifiable, 4 with no public source.
- **Safeguard:** the checks were tuned on the full data, so the accuracy of `auto_verified` rows is estimated only from Luc's pre-registered random spot-check (D016), which none of this tuning could influence.
- **Luc's queue:** 51 rows, about 6.5 h at planning estimates: 10 random (check every field), 20 flagged (check the flagged fields), 17 quick (confirm one characterisation), 4 read by hand.

### D022: Privacy sign-off (26 Oct 2026)
- Luc signed off PRIVACY.md with decisions **A1** (a dedicated corrections email, which Luc will create, plus GitHub issues), **B1** (no case titles for self-represented parties on the site) and **C1** (no self-represented parties' names in the public repo), and approved sections 1–4.
- **C1 in practice:**
  - **Kept off GitHub:** Charlotin's CSVs, the filtered case list, the download manifest (its URLs contain case names), the Pass B working files, Luc's review decisions and the draft corrections for Charlotin. All are gitignored.
  - **Published instead:** SHA-256 hashes (`raw/SHA256SUMS.txt`, `data/interim/doc_hashes.csv`), so anyone can confirm they hold identical files.
  - **Public tracker:** `data/tracker.csv` withholds case titles wherever our extraction *or* Charlotin's coding shows a self-represented party (protective). The full version stays local in `data/interim/tracker_full.csv`.
  - **Test fixtures:** two tests that used real case names now use invented ones.
  - **History:** the one existing commit is rewritten so that no version in the repo contains these files. Because GitHub can keep a replaced commit reachable by its ID, the private GitHub repo was deleted and published again rather than force-pushed. On 26 Oct 2026 Luc deleted the old `ai-in-courts` repo and published the rewritten history as the private repo `Ai-in-the-Courts` (one commit, b58d0a7).
- **Status:** Luc.

### D023: Luc's answers to the open questions (26 Oct 2026)
- **Tracker review scope:** option A, the 10 pre-registered random rows only. Flagged and hand-only rows are not reviewed for R1, so they publish only facts read by script and Charlotin's coding.
- **Rules matrix check:** Luc reads each cell next to its quoted paragraph (D019).
- **Hand-collected instruments** (Federal Court, FCFCOA, FWC, ART, County Court, VCAT, QCAT, WA District Court, WA SAT): collected by Luc **before** launch.
- **Checklist:** approved as is.
- **Drafts:** Claude drafts both the methods paper and a fact pack for Luc's practice note.
- **About page:** no extra wording about who did the spot-check.
- **GitHub username:** kept.
- **AustLII link format** (`/cgi-bin/viewdoc/au/cases/<jurisdiction>/<CODE>/<year>/<number>.html`): Luc confirmed it opened the right decision. These links are generated for people to click; AustLII is never fetched in code.
- **Corrections email:** ai.courts.corrections@proton.me, a dedicated Proton Mail account (Gmail refused Luc's phone number for verification). It is on the site and in CORRECTIONS.md.
- **D007:** reopened (see D007).

### D024: Launch before AustLII replies (26 Oct 2026)
- **Luc:** launch R1 before AustLII answers the D007 question.
- **Rule applied:** D007 fallback (iii), with one carve-out. Fields the AI extracted from an AustLII-printed copy are not published (`details_withheld`). Rows Luc has checked against the judgment himself are published, because their values rest on his reading, not on the AI processing alone. Facts read by script (citation, court, date) and Charlotin's coding are published for every row.
- **Effect at the time of writing:** 63 auto-verified rows are held back; 2 rows from non-AustLII copies publish extracted details. Luc's 10 spot-checked rows (all from AustLII copies) will publish once he has checked them.
- **Checklist statistic:** now computed from Charlotin's own coding of the Australian rows (55 of 108, 50.9%) rather than from our extraction. It is independent of the AustLII question, and its sample is much larger (108 rows instead of 2).
- **Launch condition:** the site and methods paper say "we are asking AustLII", so Luc must have sent the email before launch.
- **If AustLII says yes:** remove the hold (`WITHHOLD_AI_FIELDS_FROM_COPIES` in `scripts/12_build_tracker.py`) and rebuild. **If no:** delete the AI-derived fields for those rows and record it in CHANGELOG.md.
- **Status:** Luc.

### D025: Spot-check and rules check completed by Luc (26 Oct 2026)
- **Spot-check (10 pre-registered random rows):**
  - Fields needing judgement: 72 of 79 correct, 91.1% (Wilson 95% 82.8–95.6%), with 1 unsure.
  - Header facts: 50 of 50.
  - 4 of 10 rows had every judgement field marked correct.
  - Errors were omissions (a missing error type or impugned citation) and over-calls: "submissions_disregarded" in 3 rows where the court had not disregarded the submissions, and "found_by_court" where the court only suspected AI use. These patterns also bear on the 55 auto-verified rows still held back (D024), so check them before release.
- **Review-page bug:** the spot-check page also saved a hidden Rules-tab box as a field named "undefined", marked correct, in all 10 decisions. It was removed (backups kept locally), the page was fixed, and the accuracy above excludes it.
- **Corrections:** Luc wrote his corrections as prose. They were translated into the tracker's fixed values in `data/review/structured_corrections.json`.
  - Applied (5): each follows an explicit instruction in his notes.
  - Awaiting Luc's choice (2, both AIC-0060): the categories for two impugned citations, and the consequence. Those fields are published blank meanwhile.
  - Unsure fields are published blank.
- **Rules:** Luc checked all 5 instruments and rewrote 6 cells more fully. 15 supporting quotes were added for the paragraphs his wording cites, and all 90 quotes verify inside the cited paragraphs.
- **One held correction:** Luc's Queensland PD 5 "banned or cautioned uses" text is identical to his WA PD 9.21 text and describes WA provisions. It is held in `data/review/rules_holds.json` with the draft wording kept, until he confirms.
- **Status:** Luc (results); two choices and the Queensland cell await Luc.

### D026: Most hand-collected instruments fetched by script after all (26 Oct 2026)
- **Luc asked Claude to collect the instruments.** Each site's robots.txt was checked first. Fetched (6): FCFCOA PD-AI, ART (Use of Generative AI) Practice Direction 2026, VCAT PNVCAT11, QCAT PD 10 of 2025, the WA District Court's practice directions and practice notes, and WA SAT's practice-notes list.
- **Left to Luc (3),** because Claude does not work around bot blocks:
  - the Federal Court (HTTP 403, even for robots.txt);
  - the Fair Work Commission (HTTP 403 to automated requests);
  - the County Court of Victoria (JavaScript-built page).
- **New rows drafted** for FCFCOA, ART, VCAT and QCAT from the full texts, with 72 supporting quotes.
  - QCAT PD 10 is close to, but not identical with, Supreme Court PD 5: self-represented litigants "must also try to ensure" accuracy, and the consequences add doubt about the reliability of submissions. It therefore has its own row.
- **No AI guidance found:** the WA District Court (General and Civil Practice Directions, 8 Dec 2025; Practice Notes (General)) and WA SAT (12 practice notes). These rows read "No specific guidance found as at 26 October 2026", per the brief, with the documents searched listed.
- **Parser fix:** a paragraph number is now accepted only as a plausible next number (n to n+1 or n+2; 9 to 9A to 9B; 4.20 to 4.21 or 5.1). In QCAT, a wrapped line beginning "41 and 57 of the Barristers' Conduct Rules" had been read as paragraph 41. All 162 quotes now verify, including the earlier instruments re-checked under the stricter rule.
- **County Court of Victoria:** its page is built with JavaScript but its robots.txt allows access, so the document link was read in a browser and the Word file fetched by script: PNCCV 1-2026, version 1.0 dated 5 June 2026. Word keeps its paragraph numbers in styles, not in the text, so `aic/docxnum.py` rebuilds them from the file's own list definition ("%1." and "%1.%2", with unnumbered Heading 2 sub-headings; switched-off numbering, `numId 0`, respected). The note closely mirrors Supreme Court of Victoria SC Gen 25, so Luc's checked wording for SC Gen 25 is reused where the text is the same. All 179 quotes verify.
- **Left to Luc:** the Federal Court and the Fair Work Commission only.
- **Status:** drafts await Luc's check in the Rules tab; the no-guidance rows await his confirmation.

### D027: Luc's QCAT consequences note turned into cell text (26 Oct 2026)
- **What Luc saved:** for QCAT PD 10 "consequences", a note combining an instruction with new wording: "Apply the same correction as for the Queensland Supreme Court. Replace the practitioner sentence with the following. Practitioners responsible for … may face regulatory referral, a requirement to show cause against personal costs, or both."
- **Problem:** the build replaced the whole cell with Luc's value, which would have published the instruction itself.
- **Applied:** `data/review/rules_overrides.json` holds the final cell text, with Luc's note kept beside it. The practitioner sentence is Luc's wording; the parties sentence is kept as drafted, because he asked to replace only the practitioner sentence. `scripts/11_build_rules.py` uses the override text in place of the raw note. The cell's existing quotes (paragraphs 14 and 17) still cover it, and all 179 quotes verify.
- **Queensland Supreme Court PD 5:** Luc had marked its consequences cell correct and saved no correction for it, so "the same correction as for the Queensland Supreme Court" was unclear. PD 5 paragraph 14 is word for word QCAT paragraph 14, so his practitioner sentence fits it too. Asked, Luc said that where a correction is unclear or belongs elsewhere, Claude should apply it. His sentence is now used for PD 5 as well (also in `rules_overrides.json`), and PD 5's own parties sentence (paragraph 17) is kept. The District Court and P&E Court rows follow PD 5.
- **Spelling:** "nonexistent" in Luc's sentence is spelt "non-existent", as in both instruments.
- **Status:** Luc.

### D028: Federal Court and Fair Work Commission instruments, saved by Luc (26 Oct 2026)
- **Collected:** Luc saved both in his own browser into `rules_inbox/` (not committed). `scripts/10_fetch_rules.py --inbox` copies them to `cache/rules/` and records their SHA-256 in the manifest, with the status "saved by Luc in his browser".
  - **Federal Court GPN-AI** (16 April 2026): the Court publishes it only as a web page, so Luc printed the page to PDF (Safari, 26 Oct 2026). The page's running header and URL footer are stripped before checking.
  - **Fair Work Commission Guidance Note** (published 24 August 2026; commenced 20 October 2026): the final version, not the March 2026 exposure draft.
- **Rows drafted** from the full texts, with 53 supporting quotes. Paragraph numbers were read from each document's own numbering: 1.1 to 7.2 for the FCA and 1 to 46 for the FWC. All 233 quotes in the matrix verify inside the cited paragraphs.
- **Drafting choices:**
  - FCA: "must not occur" (paragraph 4.15) is recorded as banned; "should" wording is recorded as cautioned.
  - FWC: written mostly as "must" requirements, so disclosure and verification are recorded as mandatory. Its privacy and witness-statement wording is "should not", so it is recorded as cautioned, not banned.
  - The FWC's unnumbered boxes, on false or misleading information being an offence, are not cited, because a paragraph number would misplace them.
- **VCAT correction (Luc, Rules tab):** Luc's note asked to add "including whether the tool was open loop or closed loop" after "the GenAI tool used". This was applied through `rules_overrides.json`, with a supporting quote from paragraph 23(a). The note's last part ("Banned or cautioned uses. Fair. …") is his comment on the next cell, which he marked fair, so it is not cell text.
- **Status:** Luc checked FCFCOA, ART, VCAT, the County Court, the FCA and the FWC (all 12 instruments in the Rules tab; FCA and FWC marked fair throughout).
