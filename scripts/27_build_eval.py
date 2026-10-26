"""Build the CiteCheck evaluation items (case citations), before any matcher exists.

Brief (R2 "Evaluation"), and DECISIONS.md D029-D032:
  - real citations, as judges wrote them, from the reserved evaluation sources
    (eval/eval_sources.csv), found with the independent patterns below, never with the
    shipped TypeScript parser;
  - synthetic corruptions from aic/corrupt.py (committed first) of those real citations that
    name their parties and that the corpus holds (corrupting an uncovered citation only
    yields another uncovered one);
  - a 60/40 dev/held-out split by source document with a fixed seed; any authority that
    ends up in both splits is dropped from both, and the number is reported.
Fabricated citations from the tracker, statute items and Luc's adversarial items are added by
scripts 28-30 once Luc has checked them.

Output (committed: citation strings, labels and source MNC only, no surrounding text):
  eval/items_cases.csv  id, split, kind, origin, corruption, citation, label, source_mnc, authority
Labels (relative to the corpus at 10 March 2025):
  real items:      exists | no_record_in_range | outside_coverage | not_in_report_index
                   (existence only: judges name parties in many ways, so a real citation's label
                   does not compare names)
  synthetic items: aic.corrupt labels (exists_other_parties, no_record_in_range, ...)
"""

import csv
import gzip
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aic import ROOT  # noqa: E402
from aic.corrupt import MNC_TYPES, REPORT_TYPES, CaseCite, corrupt  # noqa: E402
from aic.courts import courts  # noqa: E402

SEED = 20261026
REAL_PER_KIND = 300  # about 600 real citations (brief)
SYNTH_TOTAL = 400  # about 400 synthetic corruptions (brief)
DEV_SHARE = 0.6

# --- independent extraction patterns (deliberately not the shipped parser) ---------------
MNC_CORE = re.compile(r"\[(?P<y>(?:19|20)\d\d)\]\s+(?P<c>[A-Z][A-Za-z0-9]{1,15})\s+(?P<n>\d{1,6})(?!\d)")
REPORT_CORE = re.compile(
    r"(?P<b>[(\[])(?P<y>(?:18|19|20)\d\d)[)\]]\s+(?:(?P<v>\d{1,4})\s+)?"
    r"(?P<s>SR\s\(NSW\)|[A-Z][A-Za-z]{0,5}(?:\s[A-Z][A-Za-z]{0,5}){0,2})\s+(?P<p>\d{1,5})(?!\d)")
YEAR_ONLY_SERIES = {"AC", "QB", "KB", "Ch", "VR", "Fam", "P", "VLR"}
# Report series sometimes written "[year] SERIES page" without a volume; never court codes.
REPORT_ABBRS = {"CLR", "ALR", "ALJR", "FCR", "FLR", "NSWLR", "SASR", "WAR", "ACTR", "NTR", "IPR", "ALD", "IR",
                "LGERA", "ACSR", "ACLC", "ATR", "ATC", "MVR", "WLR", "NZLR"}
MONTHS = {"January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December", "Jan", "Feb", "Mar", "Apr", "Jun", "Jul", "Aug", "Sep", "Sept", "Oct", "Nov", "Dec"}
MNC_PIN = re.compile(r"(?:\s*,?\s*(?:at\s+)?\[\d{1,4}\](?:\s*[-–]\s*\[\d{1,4}\])?)?")
REPORT_PIN = re.compile(r"(?:\s*(?:,|at)\s*\d{1,5}(?:\s*[-–]\s*\d{1,5})?)?")
PARTY_WORD = re.compile(r"^(?:[A-Z][\w'’./&-]*|\(No\.?|\d+\)|\([A-Za-z]+\)|v\.?|of|and|the|for|&|de|van|ex|parte|re)$")
LEADS = {"In", "See", "Cf", "Also", "Following", "Applying", "Per", "And", "But", "Compare", "As", "Under", "Contra",
         "Thus", "However", "Accordingly"}


def parties_before(text: str, start: int) -> int | None:
    """Start offset of a party name ending at start, by a simple word-run rule; None if absent."""
    window = text[max(0, start - 160):start]
    cut = max(window.rfind(". "), window.rfind(": "), window.rfind("? "), window.rfind("\n"))
    if cut >= 0:
        window = window[cut + 2:]
    words = list(re.finditer(r"\S+", window))
    keep = 0
    for m in reversed(words):
        w = m.group(0).rstrip(",")
        if m.group(0).endswith(",") and keep:
            break
        if w.endswith(";") and keep and words[len(words) - keep].group(0) in ("Ex", "Re"):
            w = w[:-1]  # "Re Wakim; Ex parte McNally"
        if not PARTY_WORD.match(w):
            break
        keep += 1
    run = words[len(words) - keep:]
    while run and (run[0].group(0) in LEADS or run[0].group(0)[0].islower()):
        run = run[1:]
    if not run:
        return None
    phrase = " ".join(m.group(0) for m in run)
    if " v " not in f" {phrase} " and " v. " not in f" {phrase} " and not phrase.startswith(("Re ", "In re ")):
        return None
    return start - len(window) + run[0].start()


def extract(text: str, own_mnc: tuple[str, int, int]) -> list[dict]:
    """Case citations in one judgment, as written (parties + citation + pinpoint)."""
    known = courts()
    out = []
    flat = re.sub(r"\s+", " ", text)
    for m in REPORT_CORE.finditer(flat):
        s = m.group("s")
        if s.split()[0] in MONTHS:
            continue
        no_vol = m.group("v") is None
        if m.group("b") == "[" and no_vol and s not in REPORT_ABBRS \
                and (s in known or (s.isupper() and len(s) >= 3 and " " not in s)):
            continue  # an MNC, read below
        if sum(ch.isupper() for ch in s) < 2 and s not in YEAR_ONLY_SERIES:
            continue
        end = m.end() + len(REPORT_PIN.match(flat, m.end()).group(0))
        p = parties_before(flat, m.start())
        out.append({"kind": "report", "start": p if p is not None else m.start(), "core": m.start(), "end": end,
                    "has_parties": p is not None,
                    "authority": f"{s}|{m.group('v') or ''}|{int(m.group('p'))}", "year": int(m.group("y")),
                    "series": s, "volume": int(m.group("v")) if m.group("v") else 0, "page": int(m.group("p")),
                    "square": m.group("b") == "["})
    for m in MNC_CORE.finditer(flat):
        court, year, number = m.group("c"), int(m.group("y")), int(m.group("n"))
        if (court, year, number) == own_mnc or court in YEAR_ONLY_SERIES or court in REPORT_ABBRS:
            continue
        end = m.end() + len(MNC_PIN.match(flat, m.end()).group(0))
        p = parties_before(flat, m.start())
        out.append({"kind": "mnc", "start": p if p is not None else m.start(), "core": m.start(), "end": end,
                    "has_parties": p is not None,
                    "authority": f"{court}|{year}|{number}", "year": year, "court": court, "number": number})
    for c in out:
        c["citation"] = flat[c["start"]:c["end"]].strip()
        c["parties"] = flat[c["start"]:c["core"]].strip() if c["has_parties"] else ""
    return out


# --- ground truth from the indexes (local copies with readable titles) -------------------
class Ground:
    def __init__(self) -> None:
        self.mnc: dict[tuple[str, int, int], str] = {}
        self.top: dict[tuple[str, int], int] = {}
        known = set(courts())
        with gzip.open(ROOT / "cache/corpus/decisions.csv.gz", "rt", newline="") as f:
            for r in csv.DictReader(f):
                if r["court"] in known:
                    k = (r["court"], int(r["year"]), int(r["number"]))
                    self.mnc[k] = r["title"]
                    self.top[k[:2]] = max(self.top.get(k[:2], 0), k[2])
        raw = json.loads((ROOT / "cache/corpus/reports_raw.json").read_text())
        self.reports = {k: list(e["names"]) for k, e in raw.items() if e["n"] >= 2}
        self.series = {k.split("|")[0] for k in self.reports}

    def mnc_parties(self, court, year, number):
        return self.mnc.get((court, year, number))

    def mnc_max(self, court, year):
        return self.top.get((court, year))

    def report_parties(self, series, volume, page):
        return self.reports.get(f"{series}|{volume or ''}|{page}")

    def report_series(self):
        return self.series


def series_canonical(written: str, known: set[str]) -> str:
    key = written.replace(" ", "").replace(".", "").upper()
    for s in known:
        if s.replace(" ", "").upper() == key:
            return s
    return written


def real_label(c: dict, g: Ground) -> str:
    if c["kind"] == "mnc":
        top = g.mnc_max(c["court"], c["year"])
        if top is None or c["number"] > top:
            return "outside_coverage"
        return "exists" if g.mnc_parties(c["court"], c["year"], c["number"]) else "no_record_in_range"
    series = series_canonical(c["series"], g.series)
    if series not in g.series:
        return "outside_coverage"
    return "exists" if g.report_parties(series, c["volume"], c["page"]) else "not_in_report_index"


def main() -> None:
    rng = random.Random(SEED)
    sources = {r["version_id"]: r for r in csv.DictReader((ROOT / "eval/eval_sources.csv").open())}
    ids = sorted(sources)
    rng.shuffle(ids)
    split_of = {vid: ("dev" if i < round(DEV_SHARE * len(ids)) else "heldout") for i, vid in enumerate(ids)}

    pool: dict[str, list[dict]] = {"mnc": [], "report": []}
    with (ROOT / "cache/corpus/corpus.jsonl").open("rb") as f:
        for line in f:
            if b'"type": "decision"' not in line[:400] and b'"type":"decision"' not in line[:400]:
                continue
            d = json.loads(line)
            src = sources.get(d["version_id"])
            if not src:
                continue
            own = (src["court"], int(src["year"]), int(src["number"]))
            found = extract(d["text"] or "", own)
            for kind in ("mnc", "report"):
                cands = [c for c in found if c["kind"] == kind]
                if cands:  # at most one of each kind per judgment, to spread the set
                    c = random.Random(f"{SEED}:{d['version_id']}:{kind}").choice(cands)
                    c.update(source=d["version_id"], source_mnc=f"[{own[1]}] {own[0]} {own[2]}")
                    pool[kind].append(c)
    g = Ground()
    real = []
    for kind in ("mnc", "report"):
        cands = sorted(pool[kind], key=lambda c: c["source"])
        real += rng.sample(cands, min(REAL_PER_KIND, len(cands)))
    for c in real:
        c.update(origin="real", corruption="", label=real_label(c, g), split=split_of[c["source"]])

    # synthetic corruptions of real citations that name their parties and that the corpus holds
    donors = [c["parties"] for c in real if c["parties"]]
    court_choices = ["HCA", "FCA", "FCAFC", "NSWSC", "NSWCA", "NSWCCA", "NSWDC", "NSWLEC", "NSWCATAD", "NSWCATAP",
                     "VSC", "VSCA", "QSC", "QCA", "WASC", "SASC"]
    with_parties = [c for c in real if c["parties"] and c["label"] == "exists"]
    types = [("mnc", t) for t in MNC_TYPES] + [("report", t) for t in REPORT_TYPES]
    per_type = SYNTH_TOTAL // len(types)
    synth = []
    for kind, ctype in types:
        made = 0
        same_kind = [x for x in with_parties if x["kind"] == kind]
        for c in rng.sample(same_kind, len(same_kind)):
            if made >= per_type:
                break
            if kind == "mnc":
                cite = CaseCite(c["parties"], "mnc", c["year"], court=c["court"], number=c["number"])
            else:
                cite = CaseCite(c["parties"], "report", c["year"], series=series_canonical(c["series"], g.series),
                                volume=c["volume"], page=c["page"], square=c["square"])
            item = corrupt(cite, ctype, g, rng, donors=donors, courts=court_choices)
            if item is None:
                continue
            synth.append({**c, "origin": "synthetic", "corruption": ctype, "citation": item.corrupted,
                          "label": item.label})
            made += 1

    items = real + synth
    splits_by_authority = defaultdict(set)
    for c in items:
        splits_by_authority[c["authority"]].add(c["split"])
    leaked = {a for a, s in splits_by_authority.items() if len(s) > 1}
    kept = [c for c in items if c["authority"] not in leaked]
    kept.sort(key=lambda c: (c["split"], c["origin"], c["kind"], c["corruption"], c["source_mnc"]))
    with (ROOT / "eval/items_cases.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "split", "kind", "origin", "corruption", "citation", "label", "source_mnc", "authority"])
        for i, c in enumerate(kept, 1):
            w.writerow([f"C{i:04d}", c["split"], c["kind"], c["origin"], c["corruption"], c["citation"], c["label"],
                        c["source_mnc"], c["authority"]])
    summary = {
        "candidate_judgments_with_mnc": len(pool["mnc"]), "candidate_judgments_with_report": len(pool["report"]),
        "real": len(real), "synthetic": len(synth), "authorities_in_both_splits_dropped": len(leaked),
        "items_dropped_with_them": len(items) - len(kept), "items": len(kept),
        "by_split_origin": Counter(f"{c['split']}/{c['origin']}" for c in kept),
        "real_labels": Counter(f"{c['kind']}:{c['label']}" for c in kept if c["origin"] == "real"),
        "synthetic_labels": Counter(f"{c['corruption']}:{c['label']}" for c in kept if c["origin"] == "synthetic"),
    }
    (ROOT / "eval/items_cases_summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
