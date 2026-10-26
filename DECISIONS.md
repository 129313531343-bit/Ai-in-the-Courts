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

## Release 2: CiteCheck AU

### D029: Release 2 plan, sources re-checked and toolchain (26 Oct 2026)
- **Dates (brief's day numbers):**
  - R2 due day 18, Wed 11 Nov 2026.
  - Stretch gate day 14, Sat 7 Nov.
  - R1 went live on day 2, so R2 starts on day 2 rather than day 8.
- **Sources re-checked 26 Oct 2026:**
  - **Open Australian Legal Corpus:**
    - Version: v7.1.0. Hugging Face revision `ef45e3fec41a960919a31149eee6dab9aa39f725`, last modified 7 Mar 2026.
    - File: `corpus.jsonl`, 9,401,179,433 bytes, SHA-256 `5abc64a3ad35a44eca65706babd63d1095c29ebebf3f5c588beb56612097b758`.
    - Contents: 232,560 documents, current to 10 March 2025. Decisions: HCA 8,096, Federal Court 63,749, NSW Caselaw 117,371. As the brief says, there is no Vic, Qld, WA, SA or Tas case law.
    - Handling: downloaded at that pinned revision into `cache/corpus/` (gitignored) and streamed line by line. No judgment text is committed.
  - **Corpus licence (LICENCE.md):**
    - The collection is CC BY 4.0.
    - HCA material may be reproduced in unaltered form for personal or non-commercial use.
    - FCA judgments may be reproduced unaltered, with acknowledgement.
    - NSW Caselaw use must be accurate, not presented as official, consistent with the current official version, compliant with suppression orders, and must exclude external robots from indexing.
    - Consequence: the site's `/data/` gets robots Disallow plus an `X-Robots-Tag: noindex` header, the brief's "Not an official version" banner, and an "as at 10 March 2025" date on every record. Names in the index are decision E1 below.
  - **Federal Register of Legislation API:**
    - Titles query `/v1/titles?$filter=collection eq 'Act' and name eq '…'` works.
    - Former names are in the `nameHistory` field. For example, C2004A00109 lists Trade Practices Act 1974, then Competition and Consumer Act 2010 from 1 Jan 2011.
    - The API returns `Access-Control-Allow-Origin` for the site's origin, so the browser can call it directly.
- **Toolchain** (exact versions, each published at least two weeks before use):
  - TypeScript 6.0.3 (typescript-eslint 8.71.1 supports TypeScript below 6.1, so not 7.x);
  - Vite 8.3.4, Vitest 5.0.3, pdfjs-dist 6.4.299, mammoth 1.13.0;
  - ESLint 10.12.0 with @eslint/js 10.0.1, Playwright 1.64.0, @types/node 24.19.2;
  - Node 24.22.1.
  - Python stays 3.14 in `~/.venvs/ai-in-courts` (the brief says 3.12). R1 already runs on 3.14 and none of the packages need 3.12. Logged here so the difference is visible.
- **Layout:**
  - `citecheck/`: the TypeScript package. `src/core/` holds the parser and matcher, imported by both the site and the Node evaluation harness.
  - `scripts/2x_*.py`: the data build (corpus scan, indexes, evaluation items).
  - `aic/corrupt.py`: the synthetic corruption generator, committed before any matcher code.
  - `eval/`: the frozen evaluation set (citation strings, labels and source MNC only).
- **Evaluation independence:** the real citations in the evaluation set are found in the eval-source judgments with a separate, deliberately broad Python pattern set, not with the shipped TypeScript parser. Citations the parser cannot read then count against it, instead of never entering the set.
- **Status:** Claude.

### D030: Corruption generator fixed before the matcher (26 Oct 2026)
- **What:** `aic/corrupt.py` with tests in `tests/test_corrupt.py`. It is committed before any CiteCheck parser or matcher code, as the brief requires. The commit's timestamp is the record.
- **Corruption types** (one change per item):
  - MNC: wrong number (another recorded case), in-range gap, number above the court-year maximum, year ±1–3, other court.
  - Reports: page moved, volume moved.
  - Both: one party replaced, all parties from another real case.
- **Labels come from the ground truth (the indexes), not from the matcher:**
  - `exists_same_parties`, `exists_other_parties`, `no_record_in_range`, `outside_coverage`, `not_in_report_index`;
  - they are relative to the corpus as at 10 March 2025.
- **Rejected alternative:** labelling items by the four states the tool should return. That would build the tool's own thresholds (such as the gap-rate cut-off, which is tuned on dev) into the ground truth. Instead, the mapping from labels to expected states is applied at scoring time and reported.
- **Party comparison for labels:** an order-free set of identifying words, ignoring case, "Pty Ltd" and similar. It is deliberately simple and independent of the matcher's own name matching.
- **Status:** Claude.

### D031: Open choices for Luc before the indexes and the evaluation set (26 Oct 2026)
- **E1: party names in the public case index.** The site needs, for each citation, the parties recorded for it (index (a) from corpus metadata; index (b) from citing judgments). These files are public (noindexed, but downloadable).
  - (A) Titles as the corpus records them, as LawCite or AustLII show them. Matching can tolerate spelling slips, and the tool can show the matched case name. But the files would be a readable list of names from about 189,000 decisions. Some NSW titles may have been anonymised since the March 2025 snapshot, and NSW Caselaw's terms require consistency with the current official version and with suppression orders.
  - (B) Names stored only as one-way fingerprints (a hash of each normalised party word). The tool compares the words in a citation with the fingerprints, says whether the parties match, and links to the official record for the name. Nothing readable is published. Costs: a misspelt name ("Smyth" for "Smith") counts as a mismatch, measured as false alarms on dev. Fingerprints of common surnames can be guessed from a name list, so this is pseudonymisation, not anonymity.
  - Recommendation: (B). It keeps the site from republishing names, which fits the privacy line taken in R1 (D022).
- **E2: real fabricated citations for the evaluation.** The tracker holds 65 citations that courts said were fake or wrong.
  - Luc has checked 18 of them (in his 10 spot-check rows).
  - The other 47 come from AustLII-printed copies whose AI-extracted details are held back (D024). Using them needs Luc's own reading.
  - About 13 of the 65 fall inside the corpus's coverage (HCA, Federal Court or NSW, decided before 10 March 2025); the rest should come back as "cannot check".
  - (a) Luc checks the 47 against the judgments, about 1 hour. (b) Use only the 18, of which about 3 are within coverage: too few for a rate, so each would be described instead. (c) Wait for AustLII.
  - Recommendation: (a).
- **E3: AGLC edition.** The brief: "I'll confirm whether AGLC5 is out. Until then, use AGLC4." Not yet confirmed. The parser reads the AGLC4 forms, which differ little from earlier practice in what judges write.
- **Luc's answers (26 Oct 2026):** E1 (B), fingerprints; E2 (a), he checks the 47 himself; E3: not sure, so AGLC4.
- **Status:** decided by Luc.

### D032: Corpus scanned; evaluation sources reserved before any mining (26 Oct 2026)
- **Download verified:** `corpus.jsonl` matches the Hugging Face SHA-256 (D029).
- **Scan** (`scripts/21_corpus_scan.py`, metadata only):
  - 232,560 documents; 187,476 decisions carry a medium neutral citation in their title;
  - 684 repeated citations skipped (first kept);
  - 1,056 decisions have no citation in their title (HCA 777, FCA 177, NSW 102);
  - per court-year counts, highest numbers and gap rates are in `data/interim/corpus_court_years.csv`.
- **Gap rates differ by court.** Recent Federal Court and NSW Supreme Court years are under 4%, but the NSW Land and Environment Court is about 47% every year. A "no record" result is far weaker evidence there, as the brief anticipated ("a court whose gap rate is above a threshold set on dev").
- **Court codes not in the R1 table:**
  - Canonical codes of courts the corpus README lists: ACompT, ACopyT, ADFDAT, AFPDT, ATPT, IRCA, NFSC, NSWADT, NSWADTAP, NSWCC, NSWChC, NSWDDT, NSWDRGC, NSWFTT, NSWIC, NSWLC, NSWLST, NSWMT, NSWTAB, NSWCATEN and UKPCHCA. These go into the CiteCheck court table.
  - About 30 decisions use miscased or garbled codes (e.g. "FCa", "ACOPYT", "FCA1"). They are left out of the index rather than guessed into a court.
- **Evaluation sources** (`scripts/22_reserve_eval.py`, `eval/eval_sources.csv`): 3,750 of the 187,476 (2%), by simple random sample with seed 20261026. This was committed before any index was mined. Index (b) will exclude these documents.
- **Status:** Claude.

### D033: The three indexes and the evaluation's case items (26 Oct 2026)
- **Fingerprints (E1):** `aic/fingerprint.py` and its TypeScript twin `citecheck/src/core/fingerprint.ts`.
  - Each identifying word of a party name becomes the first 3 bytes of its SHA-256, in base64url.
  - Shared test vectors (`citecheck/tests/fingerprint_vectors.json`) pin both implementations to the same output; the miner checks itself against them too.
- **Index (a)** (`scripts/23_build_index_a.py`):
  - 187,443 decisions in 776 court-year files, 4.2 MiB gzipped;
  - each record holds number → date, official URL and party fingerprints;
  - the 33 decisions with garbled court codes are left out;
  - 21 court codes from the corpus were added to `data/reference/court_codes.csv`, with names taken from the corpus README. Two names are marked unconfirmed (NSWCATEN, NSWIC).
- **Index (b)** (`citecheck/scripts/mine_reports.ts`, then `scripts/25_build_index_b.py`):
  - The shipped parser read 185,466 judgments, all but the 3,750 evaluation sources: 1,783,547 report citations, 93,006 distinct.
  - The 58,912 cited by at least 2 judgments are kept, in 34 series, 1.2 MiB. Each keeps up to three party fingerprint variants and the year most often written.
  - Using the shipped parser here means the index keys are exactly what the site looks up. The evaluation's real citations are found independently (below), so this does not leak the parser into the ground truth.
- **Index (c)** (`scripts/24_build_index_c.py`): 9,059 Act titles in force at the snapshot (Cth 4,661, NSW 1,418, Tas 862, WA 816, Qld 573, SA 572, Norfolk Island 157), 0.15 MiB. State Acts are checked against it; Commonwealth Acts are checked live, with these titles as the offline fallback.
- **Budget:** 5.48 MiB of the brief's 10 MB gzipped. Checksums are in `data/interim/citecheck_index_manifest.csv`.
- **Evaluation case items** (`scripts/27_build_eval.py`, `eval/items_cases.csv`): 949 items, dev 611 and held-out 338.
  - **Real citations, as written:** 600 citations (300 MNC, 300 report) from the reserved judgments, at most one of each kind per judgment.
    - They were found with independent Python patterns (tested in `tests/test_eval_extract.py`), not the shipped parser.
    - Labels record existence only: 481 exist in the corpus, 64 are outside coverage, 8 MNCs fall in a gap, and 16 report citations are not in index (b).
  - **Synthetic items:** 396 corruptions from `aic/corrupt.py`, made only from real citations that name their parties and that the corpus holds.
  - **Split:** 60/40 by source judgment, seed 20261026. 13 authorities ended up in both splits, so their 47 items were dropped from both.
  - **Privacy:** the strings are case names as published in judgments. A scan against the tracker's self-represented parties found no tracker case; the only hits were common surnames in unrelated authorities.
- **Still to add before the freeze:** the tracker's fabricated citations (after Luc's check, E2), at least 100 statute items with labels Luc confirms, and Luc's 30 adversarial items. Then Luc inspects 60 random items plus every fabricated one and approves the freeze.
- **Status:** Claude.

### D034: Luc's check of the 47 held-back fake citations; fabricated items for the evaluation (26 Oct 2026)
- **Luc's check** (review page, Fake citations tab, saved locally): all 20 cases. 42 citations marked right, 5 corrected, and missing citations noted in 3 cases.
- **Corrections turned into fixed values** (`scripts/28_build_fabricated.py`, CORRECTIONS and ADDED, each keeping his note):
  - **AIC-0033, both citations:** label not_located, not not_stated. The court describes a false case name but qualifies its finding about genuineness ([35]–[37]). Luc's second correction had no text, and his note on the first covers the same passage, so the same label is used.
  - **AIC-0036:** footnote markers removed ("[Redacted (Second Case)]", "[Redacted (Third Case)]").
  - **AIC-0104:** wrong_pinpoint instead of exists_but_misdescribed, because the criticism concerns paragraph [7] specifically.
  - **Added:**
    - s 85(3) of the Industrial Relations Act 1996 (NSW) (AIC-0036);
    - "FWC Rule XXXX" (AIC-0038), a placeholder: not_stated with a note, not a finding of non-existence;
    - Domestic Building Contract Act 1995 (Vic) and Civil Procedure Act 2010 (Vic) (AIC-0098).

    The court's own characterisation was not given for these, so they are labelled not_stated until Luc's freeze inspection.
- **Fabricated items** (`eval/items_fabricated.csv`): 65 items.
  - Sources: the 69 citations Luc has read (18 from his spot-check, 47 checked here, 4 added), less 4 the court itself redacted, which no tool can check.
  - By kind: 26 MNC, 11 report, 7 statute, and 21 "other" (a clause, a rule, a bare section, or a case name with no citation).
  - About 15 fall within the corpus's coverage: the brief's "recall on real fabricated citations within coverage" will rest on a handful, so each will be described, not just summed.
  - Split: 39 dev, 26 held-out, by tracker decision.
- **Publication:** these strings come from rows whose AI-extracted details are otherwise held back (D024). They are published here because Luc read each one himself, which is the carve-out D024 makes.
- **Privacy:** no item shares a personal name with its own case's title. The broad scan's hits were common words (Queensland, Smith, Citizenship).
- **Status:** Luc (checks); Claude (translation).

### D035: Luc-checked fake citations published in held-back tracker rows (26 Oct 2026)
- **Luc's choice:** yes. In the 20 rows whose AI-extracted details wait for AustLII (D024), the impugned citations Luc read himself are now published (tracker.csv/json "impugned_citations"). The row's `details_withheld` note ends "impugned citations checked by Luc against the judgment", and the site's label reads "Details held back; fake citations checked by Luc".
- Every other AI-extracted field in those rows stays blank until AustLII replies. This applies D024's own carve-out (human-verified values are published) to one field rather than a whole row.
- **Single source:** `aic/impugned.py` holds Luc's corrections, so the tracker and the CiteCheck evaluation items (D034) publish the same values. It raises an error if one of Luc's notes has no fixed value, so a raw note can never be published.
- **Status:** Luc (choice); Claude (build).

### D036: Report keys include the year for square-bracket series (26 Oct 2026)
- **Found while designing the matcher:** in square-bracket series (Qd R, VR, AC, QB, KB, Ch, WLR, All ER, NZLR) the volumes run within a year, so "[1990] 1 Qd R 5" and "[1991] 1 Qd R 5" are different reports. Index (b) keyed reports by volume and page alone, which merged them.
- **Fix:** one key function, `reportKey()` in `citecheck/src/core/series.ts` and its twin `aic/series.py`: "volume|page", or "year/volume|page" for square series. Both read the series table, now in `citecheck/src/core/data/series.json`.
  - The generator's ground-truth interface (`aic/corrupt.py`) now passes the year. This was committed on its own, still before any matcher code; corruption types and labels are unchanged.
- **Rebuilt:**
  - mining gives 107,436 distinct reports (was 93,006), of which 63,282 are cited by 2+ judgments (was 58,912);
  - index (b) is 1.26 MiB, and all indexes 5.51 MiB of 10 MB;
  - the case items are now 948: 600 real and 396 synthetic, less 48 dropped for 13 authorities in both splits; dev 616, held-out 332;
  - the fabricated items are unchanged (65).
- These figures supersede the index (b) and item counts in D033.
- **Status:** Claude.

### D037: The matcher, with defaults fixed before the evaluation (26 Oct 2026)
- **Luc's choice:** a preview site before the test set is finished. The rule kept: no run against the evaluation items, and no tuning, until Luc freezes the set. The matcher was tested only on a synthetic fixture index (`citecheck/tests/match.test.ts`, 40 tests).
- **States** (`citecheck/src/core/match.ts`):
  - FOUND: a record exists, and the party names match where given.
  - MISMATCH: a record exists, but its parties differ, or an Act's title exists with another year.
  - NO_RECORD: within coverage, there is no such record.
  - CANNOT_CHECK: outside coverage. That covers a court not in the corpus, a decision after 10 March 2025, a number above the court-year maximum, a court-year whose gap rate is above the threshold, a series not indexed, a report volume above the highest cited, Victorian/ACT/NT legislation, and a state Act not found (the brief's list).
  - The site never says "verified" or "good law".
- **Defaults, chosen before any evaluation:**
  - gap-rate threshold 15%;
  - party rule "every side": each side of the case name must share an identifying word with the record, so "Smith v Brown" does not match "Smith v Jones";
  - words naming the Crown are ignored, so "R" and "The Queen" meet.
  - Both are settings to tune on dev after the freeze.
- **Report citations:** a report not in index (b) gives NO_RECORD, with the caveat that only reports cited by 2+ judgments are indexed. Rejected alternative: CANNOT_CHECK, which would make every fabricated report citation uncheckable. Above the highest volume cited, the result is CANNOT_CHECK, since the report may postdate the snapshot.
- **Commonwealth Acts:**
  - The API cannot search former names (its nameHistory filter fails server side), so the full Act list (13,747 Acts with former names and status) is downloaded once at build time (`scripts/29_fetch_cth_acts.py`, index (d), 1 request per 10 s).
  - Section numbers are checked live against the EPUB of the version in force: register id and date only, read with the platform's own decompression (`zip.ts`, `legislation.ts`).
  - Offline mode makes no request and says sections were not checked.
  - A repealed Act is FOUND with its status shown; a former name is FOUND with the current name shown.
- **State Acts:** titles in force at the snapshot only (index (c)). Sections are not checked, and the page says so.
- **Links:** the official copy (corpus URL), AustLII for MNCs (format confirmed by Luc), and the Federal Register. LawCite and JADE links wait for Luc to confirm their formats (brief).
- **Status:** Claude; thresholds to tune on dev after Luc's freeze.

### D038: CiteCheck AU preview page, and two corrections to public text (26 Oct 2026)
- **Where:** https://ai-in-australian-courts.pages.dev/citecheck/, in the same Cloudflare Pages project as Release 1, so one site and one deploy command (`wrangler pages deploy site`) cover both. The brief imagined a separate `dist` deploy; one site keeps a single address for Luc's CV.
  - Vite builds into `site/citecheck/` (gitignored), with the index files under `site/citecheck/data/`, which has robots Disallow and an `X-Robots-Tag: noindex` header.
  - Release 1's pages gain a "CiteCheck" menu link.
- **Page (`citecheck/index.html`, `tools.html`, `src/main.ts`):**
  - paste box, file reading (PDF via pdf.js, Word via mammoth, both loaded only on use), an offline switch, and results with the state, the reason, notes and links;
  - the brief's banner ("Case law as at 10 March 2025: High Court, Federal Court and NSW only. No WA, Vic, Qld, SA or Tas case law"), "Not an official version", a "Preview: not yet evaluated" label, and a coverage table built from the index;
  - a page on other tools (LawCite, JADE, PelAIkan, Lexis+ AI, Westlaw), with what CiteCheck does differently and cannot do;
  - "verified" and "good law" are never used of a result;
  - LawCite and JADE are linked only at their home pages: per-citation link formats wait for Luc to confirm them (brief).
- **Checked in a browser** (local server, 26 Oct 2026):
  - A made-up 10-citation example was checked in 1.2 s cold, including a live Federal Register section check, and each result was the expected one. For instance, *Mabo v Commonwealth* (1992) 175 CLR 1 gives a name–citation mismatch, and s 52 of the Trade Practices Act 1974 resolves to the Competition and Consumer Act 2010, which has no s 52 today.
  - Offline mode sent nothing and said that sections were not checked.
  - A test PDF and a test Word file were read and checked.
  - At phone width (375 px) there is no sideways scrolling.
- **Corrections to public text found on the way:**
  - The About page and README said every flagged tracker row was checked by hand. In fact Luc checked the 10 random rows (option A), and flagged rows stay "awaiting review".
  - The README also listed status names the tracker no longer uses.
  - Both are corrected, and the fake citations Luc read in 20 held-back rows are now mentioned.
- **Status:** Claude (build); Luc deploys.
