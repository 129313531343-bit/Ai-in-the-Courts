"""Text normalisation used wherever two texts are compared.

The same functions are applied to both sides of every comparison (a quote and
the judgment it came from), so differences in typography or PDF extraction do
not count as differences in wording.
"""

import re
import unicodedata

# NFKC already expands ligatures (U+FB01 'fi' -> 'fi') and most unusual spaces.
# These are the characters it leaves alone that PDFs and APIs render
# inconsistently.
_PUNCT = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-",
    "­": "", "​": "", "‌": "", "‍": "", "﻿": "",
})
_WS = re.compile(r"\s+")
_HYPHEN_END = re.compile(r"[A-Za-z]-$")
_LOWER_START = re.compile(r"^[a-z]")


def norm_line(s: str) -> str:
    """Normalise one line: NFKC, quotes and dashes to ASCII, whitespace collapsed."""
    s = unicodedata.normalize("NFKC", s).translate(_PUNCT)
    return _WS.sub(" ", s).strip()


def join_lines(lines: list[str], sep: str = " ") -> tuple[str, list[int]]:
    """Join already-normalised lines with `sep` (a space, or a newline for text sent to the API).

    A word broken across a line end is re-joined ("exis-" + "tence" ->
    "existence") when the next line starts with a lower-case letter. Returns
    the text and each line's start offset in it, so a match position can be
    traced back to its line.
    """
    text, starts = "", []
    for ln in lines:
        if text and _HYPHEN_END.search(text) and _LOWER_START.match(ln):
            text = text[:-1]
        elif text:
            text += sep
        starts.append(len(text))
        text += ln
    return text, starts


def norm_passage(s: str) -> str:
    """Normalise a multi-line passage (e.g. an API cited_text) to one comparable line."""
    return join_lines([x for x in (norm_line(ln) for ln in s.splitlines()) if x])[0]
