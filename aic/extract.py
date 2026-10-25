"""Parsing Pass A responses and enforcing quote support in Pass B (no API calls here)."""

import re

TAG_RE = re.compile(r"^\[([A-Z_]+)\]\s*(.*)$")


def citation_dict(c) -> dict:
    d = {"cited_text": c.cited_text, "type": c.type}
    for k in ("start_page_number", "end_page_number", "start_char_index", "end_char_index"):
        v = getattr(c, k, None)
        if v is not None:
            d[k] = v
    return d


def parse_response(content) -> tuple[str, list[dict]]:
    """Rebuild a Pass A response and attach each citation to the finding its text overlaps.

    With citations on, a response arrives as several text blocks; cited blocks
    carry a `citations` list. A finding starts at a line beginning "[TAG]" and
    runs until the next such line: cited passages often contain line breaks,
    and those continuation lines belong to the same finding. A citation belongs
    to every finding its (whitespace-trimmed) block overlaps. Cited text before
    the first tag is kept under the tag UNTAGGED, so nothing cited is dropped.
    Quote IDs (Q001, Q002, ...) are assigned in reading order.
    """
    text, spans = "", []
    for block in content:
        if block.type != "text":
            continue
        start = len(text)
        text += block.text
        if getattr(block, "citations", None):
            lead = len(block.text) - len(block.text.lstrip())
            trail = len(block.text) - len(block.text.rstrip())
            spans.append((start + lead, len(text) - trail, block.citations))
    findings, cur, pos = [], None, 0
    for line in text.split("\n"):
        end = pos + len(line)
        m = TAG_RE.match(line.strip())
        if m:
            cur = {"tag": m.group(1), "text": m.group(2).strip(), "start": pos, "end": end}
            findings.append(cur)
        elif cur is not None:
            if line.strip():
                cur["text"] = (cur["text"] + " " + line.strip()).strip()
            cur["end"] = end
        elif line.strip():
            cur = {"tag": "UNTAGGED", "text": line.strip(), "start": pos, "end": end}
            findings.append(cur)
        pos = end + 1
    for f in findings:
        a0, b0 = f.pop("start"), f.pop("end")
        f["quotes"] = [citation_dict(c) for a, b, cites in spans if a < b0 and b > a0 for c in cites]
    findings = [f for f in findings if f["tag"] != "UNTAGGED" or f["quotes"]]
    q = 0
    for f in findings:
        for c in f["quotes"]:
            q += 1
            c["quote_id"] = f"Q{q:03d}"
    return text, findings


def split_impugned(text: str) -> tuple[str, str]:
    """'<citation> || <characterisation>' -> (citation, characterisation)."""
    if "||" in text:
        cit, char = text.rsplit("||", 1)
        return cit.strip(), char.strip()
    return text.strip(), ""


def enforce_quotes(fields: dict, valid_ids: set[str]) -> tuple[dict, list[str]]:
    """Blank any Pass B value whose quote IDs are empty or not among the verified quotes.

    Returns the cleaned record and the names of the fields that were blanked.
    """
    dropped = []
    for k, v in fields.items():
        if isinstance(v, list):  # e.g. impugned_citations: a list of objects with quote_ids
            keep = [c for c in v if c.get("quote_ids") and set(c["quote_ids"]) <= valid_ids]
            dropped += [f"{k}:{c.get('citation_verbatim', '?')}" for c in v if c not in keep]
            fields[k] = keep
            continue
        filled = bool(v.get("value") or v.get("values"))
        if filled and not (v.get("quote_ids") and set(v["quote_ids"]) <= valid_ids):
            dropped.append(k)
            if "value" in v:
                v["value"] = ""
            if "values" in v:
                v["values"] = []
            v["quote_ids"] = []
    return fields, dropped


# ---- Pass B output schema -------------------------------------------------

PARTY_TYPES = ["lawyer", "self_represented", "expert", "judicial_officer", "other"]
AI_USE = ["admitted", "found_by_court", "suspected", "denied"]
ERROR_TYPES = ["non_existent_case", "non_existent_legislation", "misdescribed_authority", "false_quote",
               "wrong_pinpoint", "fabricated_fact_or_evidence", "other"]
CONSEQUENCES = ["personal_costs_order", "adverse_costs_order", "regulator_referral", "submissions_disregarded",
                "warning_or_admonishment", "application_or_appeal_dismissed", "leave_refused",
                "no_consequence_stated", "other"]
CHARACTERISATIONS = ["non_existent", "not_located", "exists_but_misdescribed", "false_quote", "wrong_pinpoint",
                     "not_stated"]
ASSERTED_BY = ["court", "party", "unclear"]  # who says the citation is false or inaccurate


def _ids() -> dict:
    return {"type": "array", "items": {"type": "string"}}


def _field(enum: list[str] | None = None) -> dict:
    value = {"type": "string", "enum": list(dict.fromkeys(enum + [""]))} if enum else {"type": "string"}
    return {"type": "object", "additionalProperties": False, "required": ["value", "quote_ids"],
            "properties": {"value": value, "quote_ids": _ids()}}


def _list_field(enum: list[str]) -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["values", "quote_ids"],
            "properties": {"values": {"type": "array", "items": {"type": "string", "enum": enum}},
                           "quote_ids": _ids()}}


def pass_b_schema() -> dict:
    props = {
        "mnc": _field(), "title_as_published": _field(), "court": _field(), "date": _field(),
        "party_type": _field(PARTY_TYPES),
        "ai_use": _field(AI_USE),
        "ai_tool_if_stated": _field(),
        "error_types": _list_field(ERROR_TYPES),
        "impugned_citations": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["citation_verbatim", "characterisation", "asserted_by", "quote_ids"],
            "properties": {"citation_verbatim": {"type": "string"},
                           "characterisation": {"type": "string", "enum": CHARACTERISATIONS},
                           "asserted_by": {"type": "string", "enum": ASSERTED_BY},
                           "quote_ids": _ids()}}},
        "consequence": _list_field(CONSEQUENCES),
        "regulator_referred": _field(["yes", "no_stated"]),
        "practice_note_cited": _field(),
        "family_law_matter": _field(["yes", "no", "unclear"]),
    }
    return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}
