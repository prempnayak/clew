"""The query library played through S1–S4 on a Nebula Gear-shaped map (handoff §9, V1)."""

from __future__ import annotations

import json

from tests.mapbuilder import (
    CART_COUPON,
    CART_EMPTY,
    CART_ITEMS,
    CHECKOUT_500,
    HOME,
    LOGIN_NEXT,
    PRODUCT,
    SEARCH,
    action,
    lead,
    nebula_map,
    state,
)

LEASE = 120_000


# -- map building -------------------------------------------------------------------------------------------
def test_upsert_state_reports_new_then_known(graph):
    r1 = graph.one(
        "Q03",
        {
            "key": HOME,
            "route": "/",
            "auth": "out",
            "fingerprint": "x",
            "name": "Home",
            "url": "/",
            "agent": "e1",
            "elements": '["a"]',
            "entry": True,
            "now": 100,
        },
    )
    assert r1["is_new"] is True and r1["read"] is False and r1["previous_elements"] is None
    r2 = graph.one(
        "Q03",
        {
            "key": HOME,
            "route": "/",
            "auth": "out",
            "fingerprint": "x",
            "name": "Home",
            "url": "/",
            "agent": "e2",
            "elements": '["a","b"]',
            "entry": False,
            "now": 200,
        },
    )
    assert r2["is_new"] is False and r2["previous_elements"] == '["a"]'
    assert graph.one("Q40")["key"] == HOME


def test_read_lock_is_exclusive_and_expires(graph):
    state(graph, HOME, "Home", entry=True)
    assert graph.run("Q03b", {"key": HOME, "agent": "e1", "now": 1000, "lease_ms": 60_000})
    assert not graph.run("Q03b", {"key": HOME, "agent": "e2", "now": 2000, "lease_ms": 60_000})
    assert graph.run("Q03b", {"key": HOME, "agent": "e2", "now": 70_000, "lease_ms": 60_000})
    graph.run("Q04", {"state": HOME, "name": "Home (logged out)", "actions": [], "now": 1})
    assert not graph.run("Q03b", {"key": HOME, "agent": "e3", "now": 999_999, "lease_ms": 60_000})


# -- claims -------------------------------------------------------------------------------------------------
def test_claims_never_duplicate_and_leases_expire(graph):
    state(graph, HOME, "Home", entry=True)
    for i in range(5):
        action(graph, HOME, f"b{i}", f"B{i}")
    claimed = [graph.one("Q06", {"agent": f"e{i}", "now": 1000, "lease_ms": LEASE}) for i in range(6)]
    keys = [c["action"] for c in claimed if c]
    assert len(keys) == 5 and len(set(keys)) == 5 and claimed[5] is None
    again = graph.one("Q06", {"agent": "e9", "now": 1000 + LEASE + 1, "lease_ms": LEASE})
    assert again is not None  # an expired claim is free work (S2)


def test_mission_priority_first(graph):
    state(graph, HOME, "Home", entry=True)
    action(graph, HOME, "low", "Low", priority=2)
    action(graph, HOME, "mission", "Mission", priority=20)
    assert graph.one("Q06", {"agent": "e1", "now": 1, "lease_ms": LEASE})["label"] == "Mission"


def test_skipped_actions_are_never_claimed(graph):
    state(graph, HOME, "Home", entry=True)
    action(graph, HOME, "logout", "Log out", status="skipped")
    assert graph.one("Q06", {"agent": "e1", "now": 1, "lease_ms": LEASE}) is None


def test_variation_round_robin(graph):
    a = nebula_map(graph)
    v = graph.one("Q06b", {"agent": "e1", "now": 1000, "lease_ms": LEASE})
    assert v["action"] in (a["open_product"], a["search_add"]) and v["instance"] == 1
    v2 = graph.one("Q06b", {"agent": "e2", "now": 1000, "lease_ms": LEASE})
    assert v2["action"] != v["action"]


def test_jobs_claim_finish_only_by_claimant(graph):
    a = nebula_map(graph)
    graph.run(
        "Q12",
        {
            "action": a["login_valid"],
            "release": "v1",
            "sig": "http_5xx|GET /checkout|500",
            "kind": "http_5xx",
            "title": "t",
            "initial_status": "new",
            "severity": "P2",
            "evidence": "{}",
            "now": 50,
        },
    )
    job = graph.one("Q13", {"sig": "http_5xx|GET /checkout|500", "release": "v1", "payload": "{}", "now": 60})
    assert job["job"].startswith("J-")
    assert graph.one("Q13", {"sig": "http_5xx|GET /checkout|500", "release": "v1", "payload": "{}", "now": 61}) is None
    j = graph.one("Q05", {"agent": "e1", "now": 100, "lease_ms": 180_000})
    assert j["kind"] == "confirm" and j["target"] == "http_5xx|GET /checkout|500"
    assert graph.one("Q05", {"agent": "e2", "now": 100, "lease_ms": 180_000}) is None
    assert graph.one("Q14", {"id": j["id"], "agent": "e2", "status": "done", "result": "x", "now": 1}) is None
    assert graph.one("Q14", {"id": j["id"], "agent": "e1", "status": "done", "result": "x", "now": 1})


# -- routes and repro -------------------------------------------------------------------------------------
def test_route_and_repro_steps(graph):
    a = nebula_map(graph)
    r = graph.one("Q10", {"from": HOME, "to": CART_COUPON})
    assert r["actions"] in (
        [a["open_product"], a["add_to_cart"], a["apply_coupon"]],
        [a["search"], a["search_add"], a["apply_coupon"]],
    )  # equal cost, either is right
    assert r["states"][0] == HOME and r["states"][-2:] == [CART_ITEMS, CART_COUPON] and r["cost"] == 3
    graph.run(
        "Q12",
        {
            "action": a["apply_again"],
            "release": "v1",
            "sig": f"rule|coupon_max_10pct|{CART_COUPON}",
            "kind": "rule",
            "title": "t",
            "initial_status": "new",
            "severity": "P1",
            "evidence": "{}",
            "now": 50,
        },
    )
    rep = graph.one("Q11", {"sig": f"rule|coupon_max_10pct|{CART_COUPON}"})
    assert rep["steps"][-2:] == [a["apply_coupon"], a["apply_again"]] and len(rep["steps"]) == 4
    details = graph.run("Q10b", {"keys": rep["steps"]})
    assert {d["key"] for d in details} == set(rep["steps"])


def test_route_to_self_and_repro_on_entry(graph):
    a = nebula_map(graph)
    r = graph.one("Q10", {"from": HOME, "to": HOME})
    assert r is None  # SPpaths yields nothing for source = target; route.py treats that as "already there"
    graph.run(
        "Q12",
        {
            "action": a["open_product"],
            "release": "v1",
            "sig": "rule|price_is_number|x",
            "kind": "rule",
            "title": "t",
            "initial_status": "new",
            "severity": "P1",
            "evidence": "{}",
            "now": 50,
        },
    )
    rows = graph.run("Q11", {"sig": "rule|price_is_number|x"})
    assert rows == [{"steps": [a["open_product"]], "states": [HOME], "cost": 0.0}]
    # a bug triggered both on the entry page and deeper: the cheapest route comes first after sorting
    graph.run(
        "Q12",
        {
            "action": a["add_to_cart"],
            "release": "v1",
            "sig": "rule|price_is_number|x",
            "kind": "rule",
            "title": "t",
            "initial_status": "new",
            "severity": "P1",
            "evidence": "{}",
            "now": 51,
        },
    )
    rows = sorted(graph.run("Q11", {"sig": "rule|price_is_number|x"}), key=lambda r: r["cost"])
    assert len(rows) == 2 and rows[0]["cost"] == 0.0


def test_broken_edges_are_routed_around(graph):
    a = nebula_map(graph)
    assert graph.one("Q10", {"from": HOME, "to": CART_ITEMS})["cost"] == 2
    graph.run("Q20", {"action": a["add_to_cart"]})
    r = graph.one("Q10", {"from": HOME, "to": CART_ITEMS})
    assert r["actions"] == [a["search"], a["search_add"]] and r["cost"] == 2


def test_importance_ranks_cart_high(graph):
    nebula_map(graph)
    assert graph.one("Q09")["states"] == 8
    rows = graph.run("Q47")
    top = max(rows, key=lambda r: r["importance"])
    assert top["key"] in (CART_ITEMS, PRODUCT, SEARCH, CART_EMPTY, LOGIN_NEXT)


# -- bugs ---------------------------------------------------------------------------------------------------
def _bug(graph, action_key, sig, release="v1", status="new", kind="pageerror", now=50):
    return graph.one(
        "Q12",
        {
            "action": action_key,
            "release": release,
            "sig": sig,
            "kind": kind,
            "title": "t",
            "initial_status": status,
            "severity": "P2",
            "evidence": "{}",
            "now": now,
        },
    )


def test_bug_dedup_and_reporter_queue(graph):
    a = nebula_map(graph)
    assert _bug(graph, a["login_valid"], "s1")["count"] == 1
    assert _bug(graph, a["login_valid"], "s1")["count"] == 2
    c = graph.one("Q15c", {"statuses": ["new", "confirmed"], "agent": "reporter", "now": 100, "lease_ms": LEASE})
    assert c["sig"] == "s1"
    assert graph.one("Q15c", {"statuses": ["new"], "agent": "r2", "now": 101, "lease_ms": LEASE}) is None
    graph.run("Q13", {"sig": "s1", "release": "v1", "payload": "{}", "now": 102})
    assert graph.one("Q15d", {"sig": "s1", "agent": "reporter", "now": 103})["reported_status"] == "confirming"
    graph.run("Q15", {"sig": "s1", "status": "confirmed", "severity": None, "title": None, "now": 104})
    c = graph.one("Q15c", {"statuses": ["confirmed"], "agent": "reporter", "now": 105, "lease_ms": LEASE})
    assert c["status"] == "confirmed"
    assert (
        graph.one("Q15b", {"sig": "s1", "number": 1, "url": "u", "title": "t", "body": "b", "now": 106})["issue"] == 1
    )
    assert graph.one("Q15c", {"statuses": ["confirmed"], "agent": "reporter", "now": 107, "lease_ms": LEASE}) is None
    # still present in a new release -> needs_comment
    graph.run("Q16", {"release": "v2", "now": 200})
    _bug(graph, a["login_valid"], "s1", release="v2")
    c = graph.one("Q15c", {"statuses": ["confirmed"], "agent": "reporter", "now": 300, "lease_ms": LEASE})
    assert c["needs_comment"] is True
    d = graph.one("Q38", {"sig": "s1"})
    assert set(d["seen_in"]) == {"v1", "v2"} and d["issue"] == 1


def test_similar_bugs_and_same_as(graph):
    a = nebula_map(graph)
    _bug(graph, a["search_add"], "regression|x", kind="regression")
    _bug(graph, a["search_add"], "pageerror|/search?q|typeerror")
    sim = graph.run("Q36", {"sig": "pageerror|/search?q|typeerror"})
    assert sim[0]["sig"] == "regression|x" and sim[0]["same_trigger"] is True
    assert (
        graph.one("Q36b", {"sig": "pageerror|/search?q|typeerror", "other": "regression|x", "reason": "r", "now": 1})[
            "same_as"
        ]
        == "regression|x"
    )


def test_tool_call_audit(graph):
    a = nebula_map(graph)
    _bug(graph, a["login_valid"], "s1")
    graph.run(
        "Q29",
        {
            "id": "T-1",
            "tool": "file_issue",
            "agent": "reporter",
            "args": "{}",
            "query_ids": ["Q15b"],
            "trace": "[]",
            "ms": 3,
            "ok": True,
            "summary": "ok",
            "now": 500,
        },
    )
    graph.run("Q29b", {"id": "T-1", "sig": "s1"})
    assert graph.one("Q29c", {"sig": "s1", "tools": ["file_issue"], "since": 400})["made"] is True
    assert graph.one("Q29c", {"sig": "s1", "tools": ["close_issue"], "since": 400})["made"] is False
    assert graph.one("Q44b", {"id": "T-1"})["bug"] == "s1"


# -- releases -----------------------------------------------------------------------------------------------
def test_release_replays_regressions_and_fixes(graph):
    a = nebula_map(graph)
    _bug(graph, a["login_valid"], "http_5xx|GET /checkout|500", kind="http_5xx")
    graph.run(
        "Q15", {"sig": "http_5xx|GET /checkout|500", "status": "filed", "severity": None, "title": None, "now": 60}
    )
    assert graph.one("Q16", {"release": "v2", "now": 1000}) == {"previous": "v1", "current": "v2"}
    assert graph.one("Q16", {"release": "v2", "now": 1001}) is None
    assert graph.one("Q49") == {"previous": "v1", "current": "v2"}
    queued = graph.one("Q17", {"previous": "v1", "release": "v2", "now": 1000})["queued"]
    assert queued == 8  # every ok v1 transition (login_valid failed in v1)
    assert graph.one("Q17", {"previous": "v1", "release": "v2", "now": 1001})["queued"] == 0
    assert graph.one("Q18", {"release": "v2", "now": 1000})["queued"] == 1
    assert graph.one("Q18", {"release": "v2", "now": 1001})["queued"] == 0
    ids = [j["id"] for j in graph.run("Q45", {"limit": 50})]
    assert len(ids) == len(set(ids)) == 9
    assert graph.one("Q39", {"kind": "replay", "release": "v2"})["pending"] == 8
    # shallow first
    first = graph.one("Q05", {"agent": "e1", "now": 1100, "lease_ms": 180_000})
    assert first["kind"] == "verify_fix"
    nxt = graph.one("Q05", {"agent": "e1", "now": 1100, "lease_ms": 180_000})
    assert nxt["target"] in (a["open_product"], a["cart_icon"], a["search"])

    # v2 outcomes: R1 breaks, everything else as before, the rename heals to the same target
    for k, t in [
        ("open_product", PRODUCT),
        ("cart_icon", CART_EMPTY),
        ("search", SEARCH),
        ("add_to_cart", CART_ITEMS),
        ("apply_coupon", CART_COUPON),
        ("apply_again", CART_COUPON),
        ("checkout_empty", LOGIN_NEXT),
    ]:
        lead(graph, a[k], t, release="v2", work_kind="replay")
    lead(graph, a["search_add"], SEARCH, release="v2", ok=False, work_kind="replay")
    lead(graph, a["login_valid"], CART_EMPTY, release="v2", work_kind="replay")  # B2 fixed: not a regression
    rows = graph.run("Q19", {"previous": "v1", "release": "v2"})
    assert [r["action"] for r in rows] == [a["search_add"]]
    assert rows[0]["was_target"] == "Cart (with items)" and rows[0]["ok"] is False
    pages = {r["page"] for r in graph.run("Q35", {"action": a["search_add"]})}
    assert pages == set()  # the cart is reached through the product page, not search
    graph.run(
        "Q21",
        {
            "action": a["add_to_cart"],
            "new_name": "add to bag",
            "new_label": "Add to bag",
            "selector": "{}",
            "text": "Renamed 'Add to cart' -> 'Add to bag' in v2",
            "fact_id": "F-1",
            "agent": "e1",
            "release": "v2",
            "now": 1200,
        },
    )
    d = graph.run("Q10b", {"keys": [a["add_to_cart"]]})[0]
    assert d["aliases"] == ["add to cart"] and d["name"] == "add to bag"
    graph.run("Q22", {"sig": "http_5xx|GET /checkout|500", "release": "v2", "now": 1300})
    ch = graph.one("Q54", {"release": "v2"})
    assert ch["renames"] == ["Renamed 'Add to cart' -> 'Add to bag' in v2"]
    assert [f["sig"] for f in ch["fixed"]] == ["http_5xx|GET /checkout|500"]
    assert graph.one("Q38", {"sig": "http_5xx|GET /checkout|500"})["fixed_in"] == ["v2"]
    edges = graph.run("Q30", {"release": "v2"})
    assert any(e["ok"] is False for e in edges)


# -- memory, missions, sessions, UI ---------------------------------------------------------------------------
def test_facts_missions_sessions(graph):
    a = nebula_map(graph)
    graph.run(
        "Q25",
        {
            "about": a["checkout_empty"],
            "kind": "precondition",
            "text": "Checkout requires login",
            "fact_id": "F-1",
            "agent": "e1",
            "release": "v1",
            "now": 10,
        },
    )
    graph.run(
        "Q25",
        {
            "about": a["checkout_empty"],
            "kind": "precondition",
            "text": "Checkout requires login",
            "fact_id": "F-2",
            "agent": "e2",
            "release": "v1",
            "now": 11,
        },
    )
    facts = graph.run("Q26", {"kinds": ["precondition"], "limit": 10})
    assert len(facts) == 1 and facts[0]["about"] == a["checkout_empty"]
    m = graph.one("Q27", {"state": CART_ITEMS, "text": "Test invalid coupon codes", "by": "human", "now": 5})
    assert m["mission"] == "M-1"
    k = action(graph, CART_ITEMS, "apply", "Apply", kind="fill_submit", case="mission-1", priority=20)
    assert graph.one("Q27b", {"mission": "M-1", "keys": [k]})["linked"] == 1
    assert graph.run("Q50")[0]["actions"] == 1
    s = graph.one(
        "Q34a", {"release": "v1", "mode": "shared", "explorers": 4, "minutes": 10, "start_from": "fresh", "now": 1}
    )
    assert s["session"] == "S-1"
    graph.run(
        "Q08",
        {
            "action": a["cart_icon"],
            "run": "RUN-1",
            "agent": "e1",
            "session": "S-1",
            "release": "v1",
            "llm_calls": 1,
            "ok": True,
            "ms": 5,
            "work_kind": "explore",
            "instance": "{}",
            "now": 2,
        },
    )
    graph.run(
        "Q08",
        {
            "action": a["cart_icon"],
            "run": "RUN-2",
            "agent": "e2",
            "session": "S-1",
            "release": "v1",
            "llm_calls": 0,
            "ok": True,
            "ms": 5,
            "work_kind": "explore",
            "instance": "{}",
            "now": 3,
        },
    )
    assert graph.run("Q32", {"session": "S-1"}) == [{"action": a["cart_icon"], "agents": 2}]
    st = graph.one("Q51", {"session": "S-1"})
    assert st == {"runs": 2, "steps": 2, "explore_steps": 2, "unique_actions": 1, "llm_calls": 1}
    assert len(graph.run("Q31", {"session": "S-1"})) == 2
    assert graph.one("Q34b", {"id": "S-1", "summary": json.dumps({"bugs": 0}), "now": 9})["session"] == "S-1"
    assert graph.run("Q46")[0]["status"] == "ended"
    assert graph.one("Q41", {"name": "run"})["v"] == 1 and graph.one("Q41", {"name": "run"})["v"] == 2


def test_ui_reads(graph):
    a = nebula_map(graph)
    graph.run(
        "Q28",
        {
            "name": "explorer-1",
            "role": "explorer",
            "model": "none",
            "session": "S-1",
            "state": "working",
            "work": a["cart_icon"],
            "now": 5,
        },
    )
    assert graph.run("Q43")[0]["name"] == "explorer-1"
    cov = graph.one("Q23")
    assert cov["states"] == 8 and cov["actions"] == 9 and cov["done"] == 9
    assert graph.run("Q24", {"limit": 3})
    det = graph.one("Q42", {"key": CART_ITEMS})
    assert det["name"] == "Cart (with items)" and len(det["actions"]) == 1
    assert len(graph.run("Q53")) == 8 + 9
    assert {r["route"] for r in graph.run("Q52")} >= {"/", "/cart", "/checkout"}
    _bug(graph, a["login_valid"], "s1")
    assert graph.run("Q33")[0]["pages"] == ["Log in"]
    assert graph.run("Q48", {"action": a["login_valid"]})[0]["target"] == CHECKOUT_500
    assert graph.one("Q37")["release"] == "v1"


def test_copy_and_reset(graph, db):
    from clew.graph.client import reset_from

    nebula_map(graph)
    dest = reset_from(db, graph.name, graph.name + "_copy")
    try:
        assert dest.one("Q23")["states"] == 8
    finally:
        dest.delete()
    assert CART_EMPTY  # keep the import used


def test_baseline_reads(graph):
    a = nebula_map(graph)
    graph.run(
        "Q08",
        {
            "action": a["cart_icon"],
            "run": "RUN-1",
            "agent": "e1",
            "session": "S-1",
            "release": "v1",
            "llm_calls": 0,
            "ok": True,
            "ms": 5,
            "work_kind": "explore",
            "instance": "{}",
            "now": 2,
        },
    )
    assert graph.run("Q56", {"session": "S-1"}) == [{"agent": "e1", "action": a["cart_icon"], "at": 2}]
    graph.run("Q04", {"state": HOME, "name": None, "actions": [], "now": 1})
    assert graph.one("Q57") == {"reads": 7, "states": 8}  # Q04 marks a page read
