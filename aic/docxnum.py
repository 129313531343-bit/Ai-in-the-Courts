"""Read a Word (.docx) instrument with its automatic paragraph numbers restored.

Word often stores numbering outside the text: a paragraph style ("Heading 1",
"Normal (numbered)") points to a list definition whose levels say how to
render the number ("%1.", "%1.%2", "(%3)"). python-docx returns the text
without those numbers, so paragraph references could not be checked. This
module follows each paragraph's style to its numbering level, counts as Word
does (a level resets every deeper level), and prefixes the rendered number.

Scope: one multilevel list per document, defined through a style link, which
is how the County Court of Victoria's practice notes are built (checked on its
AI practice note, 26 Oct 2026). Paragraphs without numbering are returned as they are.
"""

from pathlib import Path

import docx
from docx.oxml.ns import qn

_ROMAN = [(10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]


def _roman(n: int) -> str:
    out = ""
    for v, s in _ROMAN:
        while n >= v:
            out += s
            n -= v
    return out


def _fmt(n: int, kind: str) -> str:
    if kind == "lowerLetter":
        return chr(ord("a") + n - 1)
    if kind == "upperLetter":
        return chr(ord("A") + n - 1)
    if kind == "lowerRoman":
        return _roman(n)
    return str(n)


def _style_level(style) -> int | None:
    """The numbering level a paragraph style carries (following base styles), if any."""
    while style is not None:
        ppr = style.element.find(qn("w:pPr"))
        num = ppr.find(qn("w:numPr")) if ppr is not None else None
        if num is not None:
            num_id = num.find(qn("w:numId"))
            if num_id is not None and num_id.get(qn("w:val")) == "0":
                return None  # numId 0 switches numbering off (e.g. unnumbered "Heading 2" sub-headings)
            ilvl = num.find(qn("w:ilvl"))
            return int(ilvl.get(qn("w:val"))) if ilvl is not None else 0
        style = style.base_style
    return None


def _levels(document) -> dict[int, tuple[str, str]]:
    """ilvl -> (lvlText, numFmt) from the style-linked list definition."""
    numbering = document.part.numbering_part.element
    for a in numbering.findall(qn("w:abstractNum")):
        if a.find(qn("w:styleLink")) is not None:
            return {int(lv.get(qn("w:ilvl"))): (lv.find(qn("w:lvlText")).get(qn("w:val")),
                                                 lv.find(qn("w:numFmt")).get(qn("w:val")))
                    for lv in a.findall(qn("w:lvl"))}
    return {}


def numbered_lines(path: Path) -> list[str]:
    d = docx.Document(str(path))
    levels = _levels(d)
    counters: dict[int, int] = {}
    out = []
    for p in d.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        lvl = _style_level(p.style)
        if lvl is None or lvl not in levels:
            out.append(text)
            continue
        counters[lvl] = counters.get(lvl, 0) + 1
        for deeper in [k for k in counters if k > lvl]:
            del counters[deeper]
        label, _ = levels[lvl]
        for k in range(lvl, -1, -1):
            label = label.replace(f"%{k + 1}", _fmt(counters.get(k, 1), levels.get(k, ("", "decimal"))[1]))
        out.append(f"{label} {text}")
    return out
