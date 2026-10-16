"""MCP tools: validation, the filing gate and the ToolCall audit trail (handoff §14)."""

from __future__ import annotations

import json

from clew.mcp_server.tools import Tools
from clew.reporter.github import GitHub
from tests.mapbuilder import nebula_map

SIG = "http_5xx|GET /checkout|500"


def setup(graph):
    a = nebula_map(graph)
    graph.run(
        "Q12",
        {
            "action": a["login_valid"],
            "release": "v1",
            "sig": SIG,
            "kind": "http_5xx",
            "title": "GET /checkout returns HTTP 500",
            "initial_status": "new",
            "severity": "P2",
            "evidence": json.dumps({"message": "GET /checkout → 500", "agent": "explorer-1"}),
            "now": 5,
        },
    )
    return a, Tools(graph, GitHub(mode="dry_run"))


def test_unknown_signature_is_an_error_not_an_exception(graph):
    _a, t = setup(graph)
    assert t.get_bug("nope", agent="reporter")["ok"] is False
    assert t.file_issue("nope", "t", "b", ["clew"], agent="reporter")["ok"] is False


def test_filing_is_gated_on_confirmed(graph):
    _a, t = setup(graph)
    r = t.file_issue(SIG, "Checkout 500", "body", ["clew", "P2"], agent="reporter")
    assert r["ok"] is False and "confirmed" in r["error"]
    t.set_bug(SIG, "confirmed", None, None, agent="reporter")
    assert t.file_issue(SIG, "Checkout 500", "body", ["bogus"], agent="reporter")["ok"] is False
    r = t.file_issue(SIG, "Checkout 500", "body", ["clew", "P2"], agent="reporter")
    assert r["ok"] and r["issue"] == 1 and r["url"].startswith("dry-run://")
    assert graph.one("Q38", {"sig": SIG})["status"] == "filed"


def test_audit_trail_records_queries(graph):
    _a, t = setup(graph)
    r = t.repro_steps(SIG, agent="reporter")
    assert r["ok"] and "Open `/`" in r["text"] and len(r["steps"]) == 4
    call = graph.one("Q44b", {"id": r["tool_call"]})
    assert call["tool"] == "repro_steps" and call["bug"] == SIG and "Q11" in call["query_ids"]
    assert json.loads(call["trace"])[0]["qid"] == "Q38" or "Q11" in [x["qid"] for x in json.loads(call["trace"])]
    assert graph.one("Q29c", {"sig": SIG, "tools": ["repro_steps"], "since": 0})["made"] is True


def test_add_cases_validates_element_ids(graph):
    from tests.mapbuilder import CART_ITEMS

    _a, t = setup(graph)
    elements = [
        {
            "id": "c1",
            "role": "textbox",
            "name": "Coupon code",
            "kind": "field",
            "target": "coupon code",
            "region": "main",
            "count": 1,
            "href": None,
            "field_ids": [],
        },
        {
            "id": "c2",
            "role": "form",
            "name": "Apply",
            "kind": "fill_submit",
            "target": "coupon code",
            "region": "main",
            "count": 1,
            "href": None,
            "field_ids": ["c1"],
        },
    ]
    graph.run(
        "Q03",
        {
            "key": CART_ITEMS,
            "route": "/cart",
            "auth": "out",
            "fingerprint": "x",
            "name": "Cart",
            "url": "/cart",
            "agent": "t",
            "elements": json.dumps(elements),
            "entry": False,
            "now": 9,
        },
    )
    bad = t.add_cases(CART_ITEMS, ["c9"], [{"case": "x", "values": {"c1": "A"}}], agent="strategist")
    assert bad["ok"] is False
    good = t.add_cases(CART_ITEMS, ["c2"], [{"case": "lowercase", "values": {"c1": "save10"}}], agent="strategist")
    assert good["ok"] and good["actions"] == [f"{CART_ITEMS}#form:coupon code:strategist-lowercase"]
