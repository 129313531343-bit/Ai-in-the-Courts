"""A judgment as normalised lines, with page numbers and paragraph numbers.

Used to check that a quote really appears in a judgment, and to say on which
page and in which paragraph. PDF text comes from pdfplumber (MIT licence;
PyMuPDF is avoided because it is AGPL).

Steps for a PDF:
1. Read each text line with its page, left position (x0) and font size.
2. Drop page furniture: running headers/footers (the same line, digits
   ignored, at the same edge of at least half the pages) and page numbers (an
   edge line that is only a number, rising one per page).
3. Drop publisher furniture that is not part of the judgment: AustLII's
   banner and page-1 header block (database name, title line, "Last
   Updated"), AustLII URL footers, and Wikisource cover and end pages.
4. Find paragraph numbers: a line starting with "12", "12." or "[12]", in body
   font size, at the left margin. Then keep the longest run that counts up by
   one, which drops footnote numbers, numbered orders and stray numbers.

Characters printed twice to fake bold (AustLII headers do this, giving
"FFeeddeerraall") are de-duplicated by pdfplumber before extraction.

`Doc.text` joins lines with newlines: it is exactly the text sent to the API
(DECISIONS D007 option b), so a citation's character offsets index into it.
"""

import bisect
import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from rapidfuzz import fuzz

from aic.textnorm import join_lines, norm_line, norm_passage

QUOTE_PASS_SCORE = 97.0  # rapidfuzz partial_ratio, 0-100 (i.e. similarity >= 0.97)
MIN_CHARS_PER_PAGE = 200  # a page with less text than this has no usable text layer
MIN_PARA_CHAIN = 3  # fewer numbered paragraphs than this: treat as unnumbered
EDGE_LINES = 2  # lines at the top and bottom of a page checked for furniture

_PARA_TOKEN = re.compile(r"^\[?(\d{1,4})\]?\.?$")
_PAGE_NO = re.compile(r"^(?:page\s+)?-?\s*(\d{1,4})\s*-?(?:\s+of\s+\d{1,4})?$", re.IGNORECASE)
_DIGITS = re.compile(r"\d+")
PUBLISHER_EDGE = 3  # lines at each page edge checked for publisher furniture
_BANNERS = {"austlii", "australasian legal information institute"}
_LAST_UPDATED = re.compile(r"^last updated:", re.IGNORECASE)
_MNC_ANY = re.compile(r"\[(?:19|20)\d\d\]\s+[A-Z][A-Za-z0-9]{1,11}\s+\d{1,5}\b")


@dataclass(frozen=True)
class Line:
    page: int  # 1-indexed
    text: str  # normalised
    x0: float = 0.0
    size: float = 0.0  # font size of the line's first character


@dataclass
class Doc:
    lines: list[Line]
    n_pages: int
    scanned: bool = False
    text: str = field(init=False)
    starts: list[int] = field(init=False)
    markers: dict[int, int] = field(init=False)  # line index -> paragraph number

    def __post_init__(self) -> None:
        self.text, self.starts = join_lines([ln.text for ln in self.lines], sep="\n")
        self.flat = self.text.replace("\n", " ")  # same length: offsets are shared
        self.markers = paragraph_markers(self.lines)
        self._marker_idx = sorted(self.markers)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    def line_at(self, offset: int) -> int:
        return max(bisect.bisect_right(self.starts, offset) - 1, 0)

    def location_at(self, line_idx: int) -> str:
        """'' inside numbered reasons; 'front_matter' above paragraph 1 (orders, catchwords,
        cover sheet); 'unnumbered_document' if no paragraph numbering was detected at all."""
        if not self._marker_idx:
            return "unnumbered_document"
        return "front_matter" if line_idx < self._marker_idx[0] else ""

    def paragraph_at(self, line_idx: int) -> str:
        k = bisect.bisect_right(self._marker_idx, line_idx) - 1
        return str(self.markers[self._marker_idx[k]]) if k >= 0 else ""


def strip_furniture(lines: list[Line], n_pages: int) -> list[Line]:
    """Remove running headers/footers and page numbers."""
    if n_pages < 3:
        return lines
    pages: dict[int, list[int]] = defaultdict(list)
    for i, ln in enumerate(lines):
        pages[ln.page].append(i)
    edges: dict[int, str] = {}  # line index -> "top" or "bottom"
    for idxs in pages.values():
        for i in idxs[:EDGE_LINES]:
            edges[i] = "top"
        for i in idxs[-EDGE_LINES:]:
            edges.setdefault(i, "bottom")

    def masked(i: int) -> str:
        return _DIGITS.sub("#", lines[i].text.lower())

    repeated = Counter((edges[i], masked(i)) for i in edges)
    drop = {i for i in edges if repeated[(edges[i], masked(i))] >= n_pages / 2 and masked(i) != "#"}

    # Page numbers: a bare number whose difference from the page index is the
    # same on at least half the pages (so "1" on p1, "2" on p2, ...).
    offsets: dict[int, int] = {}
    for i in edges:
        m = _PAGE_NO.match(lines[i].text)
        if m:
            offsets[i] = int(m.group(1)) - lines[i].page
    if offsets:
        common, count = Counter(offsets.values()).most_common(1)[0]
        if count >= n_pages / 2:
            drop |= {i for i, off in offsets.items() if off == common}
    return [ln for i, ln in enumerate(lines) if i not in drop]


def strip_publisher(lines: list[Line]) -> list[Line]:
    """Remove furniture added by the site a copy was printed from (not by the court)."""
    if not lines:
        return lines
    drop: set[int] = set()
    p1 = [i for i, ln in enumerate(lines) if ln.page == lines[0].page]
    # AustLII page-1 header: banner, database name, title line(s), "Last Updated: <date>".
    banner = [i for i in p1[:PUBLISHER_EDGE] if lines[i].text.lower() in _BANNERS]
    if banner:
        upd = [i for i in p1[:10] if _LAST_UPDATED.match(lines[i].text)]
        drop |= set(range(banner[0], upd[0] + 1)) if upd else set(banner)
    # AustLII URL footers/headers (their truncation varies, so match the host, edge lines only).
    pages: dict[int, list[int]] = defaultdict(list)
    for i, ln in enumerate(lines):
        pages[ln.page].append(i)
    for idxs in pages.values():
        for i in idxs[:PUBLISHER_EDGE] + idxs[-PUBLISHER_EDGE:]:
            if "austlii.edu.au" in lines[i].text.lower() or lines[i].text.lower() in _BANNERS:
                drop.add(i)
    # Wikisource export: cover pages before the judgment, and the e-book end matter.
    if any("exported from wikisource" in lines[i].text.lower() for i in p1):
        by_page: dict[int, str] = defaultdict(str)
        for ln in lines:
            by_page[ln.page] += " " + ln.text
        start = next((pg for pg in sorted(by_page) if _MNC_ANY.search(by_page[pg])), lines[0].page)
        drop |= {i for i, ln in enumerate(lines) if ln.page < start}
        end = next((i for i, ln in enumerate(lines) if "e-book comes from the online library wikisource"
                    in ln.text.lower()), None)
        if end is not None:
            drop |= set(range(end, len(lines)))
    return [ln for i, ln in enumerate(lines) if i not in drop]


def paragraph_markers(lines: list[Line]) -> dict[int, int]:
    """Map line index -> paragraph number, for lines that start a numbered paragraph."""
    sized = [ln for ln in lines if ln.size > 0]
    body = 0.0
    if sized:
        weights = Counter()
        for ln in sized:
            weights[round(ln.size * 2) / 2] += len(ln.text)
        body = weights.most_common(1)[0][0]
    margin: dict[int, float] = {}
    for ln in lines:
        if ln.size >= 0.85 * body:
            margin[ln.page] = min(margin.get(ln.page, ln.x0), ln.x0)

    cands: list[tuple[int, int]] = []
    for i, ln in enumerate(lines):
        m = _PARA_TOKEN.match(ln.text.split(" ", 1)[0])
        if not m:
            continue
        if body and ln.size < 0.85 * body:  # smaller font: a footnote
            continue
        if ln.x0 > margin.get(ln.page, ln.x0) + 20:  # not at the left margin
            continue
        cands.append((i, int(m.group(1))))
    if not cands:
        return {}

    # Longest chain n, n+1, n+2, ... in reading order. On a tie the most recent
    # candidate wins, so the reasons' "1" (not the orders' "1. The appeal is
    # dismissed") is what the reasons' "2" links back to.
    best: dict[int, tuple[int, int]] = {}  # number -> (chain length, candidate index)
    length, back = [0] * len(cands), [-1] * len(cands)
    for k, (_, n) in enumerate(cands):
        prev = best.get(n - 1)
        length[k], back[k] = (prev[0] + 1, prev[1]) if prev else (1, -1)
        if n not in best or length[k] >= best[n][0]:
            best[n] = (length[k], k)
    k = max(range(len(cands)), key=lambda j: length[j])
    if length[k] < MIN_PARA_CHAIN:
        return {}
    chain = []
    while k != -1:
        chain.append(cands[k])
        k = back[k]
    return dict(reversed(chain))


def load_pdf(path: Path) -> Doc:
    import pdfplumber

    lines: list[Line] = []
    chars_per_page: list[int] = []
    with pdfplumber.open(path) as pdf:
        n_pages = len(pdf.pages)
        for pno, page in enumerate(pdf.pages, 1):
            n_chars = 0
            for tl in page.dedupe_chars().extract_text_lines(return_chars=True, strip=True):
                text = norm_line(tl["text"])
                if not text:
                    continue
                n_chars += len(text)
                size = tl["chars"][0]["size"] if tl.get("chars") else 0.0
                lines.append(Line(pno, text, float(tl["x0"]), round(float(size), 2)))
            chars_per_page.append(n_chars)
    scanned = n_pages > 0 and sum(c < MIN_CHARS_PER_PAGE for c in chars_per_page) > n_pages / 2
    return Doc(strip_publisher(strip_furniture(lines, n_pages)), n_pages, scanned)


def load_text(text: str) -> Doc:
    """A plain-text document (used for .docx, converted to text). One 'page'."""
    lines = [Line(1, t) for t in (norm_line(x) for x in text.splitlines()) if t]
    return Doc(lines, 1, False)


def docx_text(path: Path) -> str:
    """Plain text of a .docx, one paragraph per line. Word's automatic
    paragraph numbering is not part of the text, so it is lost here."""
    import docx  # python-docx

    return "\n".join(p.text for p in docx.Document(str(path)).paragraphs)


def load_any(path: Path) -> Doc:
    if path.suffix.lower() == ".pdf":
        return load_pdf(path)
    if path.suffix.lower() == ".docx":
        return load_text(docx_text(path))
    raise ValueError(f"unsupported file type: {path}")


@dataclass
class Match:
    score: float
    passed: bool
    page: int | None
    paragraph: str
    where: str  # "cited_pages", "other_pages", "not_found", "scanned", "empty_quote"


def match_quote(doc: Doc, quote: str, pages: tuple[int, int] | None = None) -> Match:
    """Find a quote in the document. Tries the cited pages first, then the whole document."""
    if doc.scanned:
        return Match(0.0, False, None, "", "scanned")
    q = norm_passage(quote)
    if not q:
        return Match(0.0, False, None, "", "empty_quote")

    def search(lo_line: int, hi_line: int) -> tuple[float, int]:
        base = doc.starts[lo_line]
        end = doc.starts[hi_line + 1] if hi_line + 1 < len(doc.starts) else len(doc.flat)
        al = fuzz.partial_ratio_alignment(q, doc.flat[base:end])
        return (al.score, base + al.dest_start) if al else (0.0, base)

    best: tuple[float, int, str] = (0.0, 0, "not_found")
    if pages and doc.lines:
        idx = [i for i, ln in enumerate(doc.lines) if pages[0] <= ln.page <= pages[1]]
        if idx:
            s, off = search(idx[0], idx[-1])
            best = (s, off, "cited_pages")
    if best[0] < QUOTE_PASS_SCORE and doc.lines:
        s, off = search(0, len(doc.lines) - 1)
        if s > best[0]:
            best = (s, off, "other_pages" if pages else "document")
    score, off, where = best
    passed = score >= QUOTE_PASS_SCORE
    li = doc.line_at(off)
    return Match(round(score, 1), passed, doc.lines[li].page if doc.lines else None,
                 doc.paragraph_at(li) if passed else "", where if passed else "not_found")
