"""Party-name fingerprints for the public CiteCheck indexes (Luc's choice E1, DECISIONS.md D031).

The site never publishes a readable party name. Each identifying word of a case title is
reduced to a short one-way fingerprint; the browser fingerprints the words of the citation
it is checking the same way and compares. The TypeScript twin is
citecheck/src/core/fingerprint.ts; tests/fingerprint_vectors.json pins both to the same
output.

  words(title):  Unicode NFKD, accents dropped, lower case, "&" read as "and", anything
                 other than a-z and 0-9 becomes a space; then drop words in STOP, single
                 characters and pure numbers. Each word kept once, in order of appearance.
  sides(title):  the title split at " v " and ";", each side reduced with words().
  fp(word):      the first 3 bytes of SHA-256(word), base64url: 4 characters.

Three bytes leave about 16.7 million possible fingerprints, so a fingerprint does not pin
down a word on its own, while the chance that a different word in a citation collides
with one of a record's few words is under one in a million. Fingerprints of common names
can still be tested against a name list: pseudonymisation, not anonymity.
"""

import base64
import hashlib
import re
import unicodedata

STOP = frozenset("""v vs versus the of and re ex parte in matter pty ltd limited inc co corp plc llc no as for by
on behalf trading ta an at to with from de du da van von der den la le""".split())
_NON_WORD = re.compile(r"[^a-z0-9]+")
_SIDES = re.compile(r"\s+v\.?\s+|\s*;\s*", re.IGNORECASE)


def words(text: str) -> list[str]:
    t = unicodedata.normalize("NFKD", text)
    t = "".join(ch for ch in t if not unicodedata.combining(ch)).lower().replace("&", " and ")
    out: list[str] = []
    for w in _NON_WORD.sub(" ", t).split():
        if len(w) > 1 and not w.isdigit() and w not in STOP and w not in out:
            out.append(w)
    return out


def fp(word: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(word.encode()).digest()[:3]).decode()


def sides(title: str) -> list[list[str]]:
    return [ws for part in _SIDES.split(title) if (ws := words(part))]


def encode_title(title: str) -> str:
    """Compact form for an index record: fingerprints joined by spaces, sides by '|'."""
    return "|".join(" ".join(fp(w) for w in side) for side in sides(title))
