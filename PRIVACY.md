# Privacy rules for the tracker

**Status: signed off by Luc Taya on 26 October 2026** (decisions A1, B1, C1; sections 1–4 approved). Sections 1–4 describe what is built; section 5 records the decisions.

## 1. Record only what the judgment says
- Every tracker field comes from the judgment itself. Each value must rest on a quote found word for word in the judgment, at a stated paragraph. Values without such a quote are discarded automatically.
- Nothing is added from outside the judgment: no news reports, social media, LinkedIn or practitioner registers, and no inferences about a person beyond the court's own words.
- `title_as_published` is the title exactly as the court published it. A name is never added, completed or reconstructed.
- Where the court only *suspected* AI use, the tracker says "suspected" (field `ai_use`). It never upgrades a suspicion to "admitted" or "found".
- Where only a *party* says a citation is false, rather than the court, the row is flagged and that claim is never presented as a court finding.

## 2. Self-represented litigants (as built)
- On the site, rows can be filtered by court, year, party type, consequence and verification status. **There is no text or name search.**
- The site's page titles, descriptions and web addresses contain no party names. Rows have neutral IDs (`AIC-0001`), not case names.
- Search engines are told not to index the tracker page or the downloadable data (`noindex`, plus `robots.txt`).
- **The tracker page and the public `tracker.csv` do not show self-represented parties' case titles** (decision B1). Each decision is identified by its medium neutral citation instead.

## 3. Family law matters
- Family Law Act 1975 (Cth) s 114Q makes it an offence to communicate to the public an account of proceedings under that Act that identifies a party, a witness, a related or associated person, or anyone else concerned in the matter. It does not apply to a communication made in accordance with a court direction or otherwise approved by a court (s 114Q(2)). Under s 114Q(3), identifying material includes names, addresses, employment details and relationships, among other things.
  - *Verified on 25 Oct 2026* against the official text on the Federal Register of Legislation: title C2004A00275, compilation No. 101 (register ID C2025C00341), in force from 10 June 2025. Section 114Q sits in Part XIVB, inserted by Act No. 87 of 2023.
- Rule: a family law row uses only the court's own anonymised title (e.g. "Mertz & Mertz (No 3)") and records nothing that the published judgment does not. No detail is added that could identify anyone, even if it is publicly available elsewhere.
- Whether a row is a family law matter is decided from the decision's own citation, not from Charlotin's "Family Court" label. Family law divisions are FedCFamC1A, 1F and 2F; FedCFamC2G is general federal law. Result: 6 family law rows (five FedCFamC1A, one FedCFamC2F). Three rows Charlotin labels "Family Court" are in fact general federal law decisions.
- Practitioner names: the tracker has no field for practitioner names. If a court's own title names a practitioner (one family law decision is titled with the practitioner's surname), the court's title is reproduced unchanged and nothing is added.

## 4. Corrections and takedown
- Requests are answered within 7 days, and every change is logged in CHANGELOG.md.
- For self-represented people, identifying detail may be removed on request even where the entry is accurate.
- The contact method is decision A below.

## 5. Decisions for Luc

**A. Corrections contact.** How do members of the public reach you?
- *A1 (recommended):* a dedicated email address you create just for this, e.g. a free Gmail or Proton account such as `aiincourts.corrections@…`, shown on the site, plus GitHub issues for people who use GitHub.
- *A2:* GitHub issues only. This is free and needs nothing new, but people without a GitHub account can't reach you, which is a barrier for a self-represented person asking for a takedown.
- Your personal email is never published unless you say so.

**B. Case titles of self-represented parties on the site.**
- *B1 (recommended, currently built):* not shown. Rows show the court's citation (e.g. "[2026] FWC 1669"), which anyone can look up. This follows the brief's rule against name searches most closely.
- *B2:* shown exactly as the court published them. This is more convenient for readers, but names become visible on the page.

**C. Names in the public GitHub repository.** When the repo is made public, the site's protections don't apply to it. As committed now, it contains self-represented parties' names in Charlotin's raw CSV files (`raw/`), our `data/tracker.csv` and the working files. GitHub pages can appear in search results.
- *C1 (recommended):* keep names out of the public repo. Charlotin's raw CSVs stay on your Mac only (the repo keeps their SHA-256 hashes and the download script, so anyone can fetch the identical file from Charlotin), and the public `tracker.csv` follows decision B. Because the repo is still private, I can remove these files from its history before it goes public. That needs one "force push", which you would approve.
- *C2:* publish as is. Charlotin already publishes these names under CC BY, so the repo adds nothing new, but it would undercut decision B.

**D. Approve sections 1–4 as written** (or tell me what to change).

---
Sign-off: Luc Taya. Decisions: A1, B1, C1, D approved. Date: 26 October 2026.
- A1: the corrections email address is to be created by Luc (pending); GitHub issues are also accepted once the repo is public.
- B1: implemented in `scripts/15_build_site.py` (titles not shown for self-represented parties).
- C1: implemented. Files containing party names are gitignored (Charlotin's CSVs, the case list, the download manifest, Pass B working files, review decisions, the draft corrections). Their SHA-256 hashes are published (`raw/SHA256SUMS.txt`, `data/interim/doc_hashes.csv`). The public `data/tracker.csv` withholds case titles wherever either our extraction or Charlotin's coding shows a self-represented party. The repo history is rewritten so that no earlier version contains these files.
