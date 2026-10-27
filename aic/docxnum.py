"""Read a Word (.docx) document with its automatic paragraph numbers restored.

Word often stores numbering outside the text: a paragraph (directly, or through its style)
points to a numbering instance (numId), which points to a list definition whose levels say
how to render the number ("%1.", "%1.%2", "(%3)"). python-docx returns the text without
those numbers, so paragraph references could not be checked. This module follows each
paragraph to its own list, counts as Word does (per numbering instance; a level resets
every deeper level), and prefixes the rendered number.

Handles: numbering set on the paragraph or inherited from its style (and base styles),
numId 0 switching numbering off, list definitions that point to a list style
(numStyleLink), and level start values. Paragraphs without numbering are returned as they
are. Checked on the County Court of Victoria's AI practice note (26 Oct 2026) and on two
judgments in Word format (Page v Long, County Court; Murray v Victoria, Federal Court;
27 Oct 2026; DECISIONS.md D042).
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
    if kind == "upperRoman":
        return _roman(n).upper()
    return str(n)


def _num_pr(ppr) -> tuple[str | None, int | None]:
    num = ppr.find(qn("w:numPr")) if ppr is not None else None
    if num is None:
        return None, None
    nid = num.find(qn("w:numId"))
    lvl = num.find(qn("w:ilvl"))
    return (nid.get(qn("w:val")) if nid is not None else None,
            int(lvl.get(qn("w:val"))) if lvl is not None else None)


def _paragraph_num(p) -> tuple[str, int] | None:
    """(numId, level) for a paragraph: its own numbering first, then its style's; None if unnumbered."""
    nid, lvl = _num_pr(p._p.pPr)
    style = p.style
    while (nid is None or lvl is None) and style is not None:
        s_nid, s_lvl = _num_pr(style.element.find(qn("w:pPr")))
        nid = nid if nid is not None else s_nid
        lvl = lvl if lvl is not None else s_lvl
        style = style.base_style
    if nid is None or nid == "0":  # numId 0 switches numbering off (e.g. unnumbered "Heading 2" sub-headings)
        return None
    return nid, lvl or 0


class _Lists:
    """numId -> levels {ilvl: (lvlText, numFmt, start)}, following numStyleLink to the list style."""

    def __init__(self, document) -> None:
        part = document.part.numbering_part.element
        self.abstract = {a.get(qn("w:abstractNumId")): a for a in part.findall(qn("w:abstractNum"))}
        self.nums = {n.get(qn("w:numId")): n.find(qn("w:abstractNumId")).get(qn("w:val"))
                     for n in part.findall(qn("w:num"))}
        self.styles = {s.style_id: s for s in document.styles}
        self.cache: dict[str, dict[int, tuple[str, str, int]]] = {}

    def levels(self, num_id: str, depth: int = 0) -> dict[int, tuple[str, str, int]]:
        if num_id in self.cache:
            return self.cache[num_id]
        a = self.abstract.get(self.nums.get(num_id, ""))
        out: dict[int, tuple[str, str, int]] = {}
        if a is not None:
            link = a.find(qn("w:numStyleLink"))
            if link is not None and depth < 3:  # the list lives in a list style: follow it
                style = self.styles.get(link.get(qn("w:val")))
                linked, _ = _num_pr(style.element.find(qn("w:pPr"))) if style is not None else (None, None)
                if linked and linked != num_id:
                    out = self.levels(linked, depth + 1)
            for lv in a.findall(qn("w:lvl")):
                text, fmt, start = lv.find(qn("w:lvlText")), lv.find(qn("w:numFmt")), lv.find(qn("w:start"))
                if text is None:
                    continue
                out[int(lv.get(qn("w:ilvl")))] = (text.get(qn("w:val")),
                                                  fmt.get(qn("w:val")) if fmt is not None else "decimal",
                                                  int(start.get(qn("w:val"))) if start is not None else 1)
        self.cache[num_id] = out
        return out


def numbered_lines(path: Path) -> list[str]:
    d = docx.Document(str(path))
    lists = _Lists(d)
    counters: dict[str, dict[int, int]] = {}
    out = []
    for p in d.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        num = _paragraph_num(p)
        levels = lists.levels(num[0]) if num else {}
        if not num or num[1] not in levels:
            out.append(text)
            continue
        nid, lvl = num
        c = counters.setdefault(nid, {})
        c[lvl] = c.get(lvl, levels[lvl][2] - 1) + 1
        for deeper in [k for k in c if k > lvl]:
            del c[deeper]
        label = levels[lvl][0]
        for k in range(lvl, -1, -1):
            label = label.replace(f"%{k + 1}", _fmt(c.get(k, levels.get(k, ("", "decimal", 1))[2]),
                                                   levels.get(k, ("", "decimal", 1))[1]))
        out.append(f"{label} {text}" if label else text)
    return out
