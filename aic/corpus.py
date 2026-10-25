"""Cached, reproducible judgment text per tracker row.

Extracting a PDF takes about a second, and the text sent to the API must be
byte-identical to the text later used to check its citations. So each
document's extracted lines are cached in cache/doctext/<row>.json (gitignored,
since it is judgment text), keyed by the source file's SHA-256 and
EXTRACTION_VERSION. Bump the version whenever doctext extraction changes;
cached text is then rebuilt rather than silently reused.
"""

import hashlib
import json
from pathlib import Path

from aic import ROOT
from aic.doctext import Doc, Line, load_any

EXTRACTION_VERSION = "2026-10-25.2"  # furniture + publisher stripping, bold de-dup, newline join
CACHE = ROOT / "cache/doctext"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def doc_for_row(row: str, local_file: str) -> Doc:
    path = ROOT / "cache/docs" / local_file
    src = file_sha256(path)
    cp = CACHE / f"{row}.json"
    if cp.exists():
        d = json.loads(cp.read_text())
        if d.get("source_sha256") == src and d.get("version") == EXTRACTION_VERSION:
            return Doc([Line(**x) for x in d["lines"]], d["n_pages"], d["scanned"])
    doc = load_any(path)
    CACHE.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps({
        "version": EXTRACTION_VERSION, "source_sha256": src, "text_sha256": doc.sha256,
        "n_pages": doc.n_pages, "scanned": doc.scanned,
        "lines": [{"page": ln.page, "text": ln.text, "x0": ln.x0, "size": ln.size} for ln in doc.lines],
    }, ensure_ascii=False))
    return doc
