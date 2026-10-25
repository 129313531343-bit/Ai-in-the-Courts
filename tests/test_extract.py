import json
from types import SimpleNamespace as NS

from aic.extract import CHARACTERISATIONS, enforce_quotes, parse_response, pass_b_schema, split_impugned


def cite(text, p1, p2):
    return NS(type="page_location", cited_text=text, start_page_number=p1, end_page_number=p2)


def block(text, citations=None):
    return NS(type="text", text=text, citations=citations)


def test_citations_attach_to_their_own_line():
    content = [
        NS(type="thinking", thinking=""),
        block("[MNC] "),
        block("[2025] VSCA 1", [cite("[2025] VSCA 1", 1, 2)]),
        block("\n[IMPUGNED] "),
        block("Smith v Jones [2020] HCA 99 || non_existent", [cite("No such case exists.", 4, 5)]),
        block("\n"),
    ]
    text, findings = parse_response(content)
    assert [f["tag"] for f in findings] == ["MNC", "IMPUGNED"]
    assert findings[0]["quotes"][0]["cited_text"] == "[2025] VSCA 1"
    assert findings[1]["quotes"][0]["cited_text"] == "No such case exists."
    assert [q["quote_id"] for f in findings for q in f["quotes"]] == ["Q001", "Q002"]


def test_block_starting_with_newline_goes_to_next_line():
    # A cited block that begins with "\n" must not be credited to the previous line.
    content = [block("[AI_ERROR] cases did not exist"),
               block("\n[CONSEQUENCE] referred to regulator", [cite("I refer the matter.", 9, 10)])]
    _, findings = parse_response(content)
    assert findings[0]["quotes"] == [] and len(findings[1]["quotes"]) == 1


def test_untagged_cited_line_is_kept():
    _, findings = parse_response([block("The court said", [cite("x", 1, 2)])])
    assert findings[0]["tag"] == "UNTAGGED"


def test_split_impugned():
    assert split_impugned("A v B [2020] FCA 1 || false_quote") == ("A v B [2020] FCA 1", "false_quote")
    assert split_impugned("A v B") == ("A v B", "")


def test_enforce_quotes_blanks_unsupported_values():
    fields = {
        "mnc": {"value": "[2025] VSCA 1", "quote_ids": ["Q001"]},
        "ai_tool_if_stated": {"value": "ChatGPT", "quote_ids": []},  # no support
        "court": {"value": "Court of Appeal", "quote_ids": ["Q999"]},  # unknown quote
        "consequence": {"values": ["regulator_referral"], "quote_ids": ["Q002"]},
        "impugned_citations": [
            {"citation_verbatim": "A v B", "characterisation": "non_existent", "quote_ids": ["Q002"]},
            {"citation_verbatim": "C v D", "characterisation": "non_existent", "quote_ids": ["Q404"]},
        ],
    }
    out, dropped = enforce_quotes(fields, {"Q001", "Q002"})
    assert out["mnc"]["value"] == "[2025] VSCA 1"
    assert out["ai_tool_if_stated"]["value"] == "" and out["court"]["value"] == ""
    assert out["consequence"]["values"] == ["regulator_referral"]
    assert [c["citation_verbatim"] for c in out["impugned_citations"]] == ["A v B"]
    assert set(dropped) == {"ai_tool_if_stated", "court", "impugned_citations:C v D"}


def test_schema_is_strict_and_enums_unique():
    def walk(node):
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])
            for v in node["properties"].values():
                walk(v)
        if node.get("type") == "array":
            walk(node["items"])
        if "enum" in node:
            assert len(node["enum"]) == len(set(node["enum"]))
    s = pass_b_schema()
    walk(s)
    json.dumps(s)
    assert "not_located" in CHARACTERISATIONS


def test_continuation_lines_belong_to_the_same_finding():
    content = [
        block("[AI_USE] Admitted "),
        block("the appellant agreed that she had used\na generative AI program", [cite("agreed ... program", 3, 4)]),
        block("\n[CONSEQUENCE] dismissed"),
    ]
    _, findings = parse_response(content)
    assert [f["tag"] for f in findings] == ["AI_USE", "CONSEQUENCE"]
    assert len(findings[0]["quotes"]) == 1 and findings[1]["quotes"] == []
    assert "a generative AI program" in findings[0]["text"]
