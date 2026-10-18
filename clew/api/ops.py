"""Operations shared by the API and the CLI: sessions, store release and reset, missions, snapshots (handoff §16).

Explorer containers are started, killed and restarted by the internal controller (clew/controller); this module
only asks it over HTTP. Without a controller (local dev), sessions still start and the swarm is run by
`python -m clew.dev` or `python -m clew.explorer.worker`.
"""

from __future__ import annotations

import json

import httpx

from clew.common.config import env, env_int, load, seed_graph, shop_url, v1_snapshot
from clew.common.ids import now_ms
from clew.explorer.extract import Candidate
from clew.graph.client import Graph, reset_from
from clew.graph.seed import seed
from clew.mcp_server.tools import CaseIn, Tools


class OpError(Exception):
    pass


def _admin() -> dict:
    return {"Authorization": f"Bearer {env('SHOP_ADMIN_TOKEN')}"}


def store_release(release: str) -> dict:
    r = httpx.post(f"{shop_url()}/__release", headers=_admin(), json={"release": release}, timeout=10)
    r.raise_for_status()
    return r.json()


def store_reset() -> dict:
    r = httpx.post(f"{shop_url()}/__reset", headers=_admin(), timeout=30)
    r.raise_for_status()
    return r.json()


def controller(path: str, payload: dict | None = None) -> dict:
    url = env("CONTROLLER_URL")
    if not url:
        return {"ok": False, "error": "no controller configured (local mode)"}
    r = httpx.post(
        f"{url}{path}", json=payload or {}, timeout=60, headers={"Authorization": f"Bearer {env('CONTROLLER_TOKEN')}"}
    )
    r.raise_for_status()
    return r.json()


def reset_map(graph: Graph) -> Graph:
    """Fresh map: GRAPH.COPY <app>_seed → the live graph (seeding first if needed)."""
    if not Graph(graph.db, seed_graph()).exists():
        return seed(graph.db, graph.name)
    return reset_from(graph.db, seed_graph(), graph.name)


def reset_all(graph: Graph) -> dict:
    store_reset()
    reset_map(graph)
    return {"ok": True, "graph": graph.name, "release": "v1"}


def snapshot(graph: Graph, name: str | None = None) -> dict:
    name = name or v1_snapshot()
    reset_from(graph.db, graph.name, name)
    return {"ok": True, "snapshot": name}


def running_session(graph: Graph) -> dict | None:
    return next((s for s in graph.run("Q46", read_only=True) if s["status"] == "running"), None)


def start_session(
    graph: Graph, explorers: int, minutes: float, mode: str = "shared", start_from: str = "fresh"
) -> dict:
    hosted = env("HOSTED_MODE", "false").lower() == "true"
    if hosted:
        explorers = min(explorers, env_int("HOSTED_MAX_EXPLORERS", 4))
        minutes = min(minutes, env_int("HOSTED_MAX_MINUTES", 10))
        today = [s for s in graph.run("Q46", read_only=True) if s["started_at"] > now_ms() - 86_400_000]
        if len(today) >= env_int("HOSTED_DAILY_SESSIONS", 30):
            raise OpError("daily session cap reached")
    if running_session(graph):
        raise OpError("a session is already running")
    if mode not in ("shared", "isolated") or start_from not in ("fresh", "continue", "v1_snapshot"):
        raise OpError("mode must be shared|isolated; start_from fresh|continue|v1_snapshot")
    if start_from == "fresh":
        reset_all(graph)
    elif start_from == "v1_snapshot":
        if not Graph(graph.db, v1_snapshot()).exists():
            raise OpError("no v1 snapshot yet (make snapshot-v1)")
        store_reset()
        reset_from(graph.db, v1_snapshot(), graph.name)
    rel = graph.one("Q37", read_only=True)
    sid = graph.one(
        "Q34a",
        {
            "release": rel["release"] if rel else "v1",
            "mode": mode,
            "explorers": explorers,
            "minutes": minutes,
            "start_from": start_from,
            "now": now_ms(),
        },
    )["session"]
    scaled = controller("/scale", {"n": explorers, "session": sid, "mode": mode})
    graph.publish("session", id=sid, status="running")
    return {"ok": True, "session": sid, "explorers": explorers, "minutes": minutes, "controller": scaled}


def stop_session(graph: Graph, sid: str | None = None) -> dict:
    s = running_session(graph) if sid is None else {"id": sid}
    if not s:
        raise OpError("no running session")
    summary = {
        "coverage": graph.one("Q23", read_only=True),
        "stats": graph.one("Q51", {"session": s["id"]}, read_only=True),
        "duplicates": len(graph.run("Q32", {"session": s["id"]}, read_only=True)),
        "bugs": [
            {"sig": b["sig"], "status": b["status"], "issue": b["issue"]} for b in graph.run("Q33", read_only=True)
        ],
    }
    graph.run("Q34b", {"id": s["id"], "summary": json.dumps(summary, default=str), "now": now_ms()})
    scaled = controller("/scale", {"n": 0})
    graph.publish("session", id=s["id"], status="ended")
    return {"ok": True, "session": s["id"], "summary": summary, "controller": scaled}


def expire_sessions(graph: Graph) -> str | None:
    """Stop the running session once its minutes are up (called periodically by the API)."""
    s = running_session(graph)
    if s and now_ms() > s["started_at"] + float(s["minutes"] or 10) * 60_000:
        stop_session(graph, s["id"])
        return s["id"]
    return None


def add_mission(graph: Graph, state: str, text: str, by: str = "human") -> dict:
    """Q27 + deterministic Strategist fallback: invalid values for the page's first form (§11.5), as
    high-priority mission actions (Q04, Q27b)."""
    row = graph.one("Q27", {"state": state, "text": text[:300], "by": by, "now": now_ms()})
    if not row:
        raise OpError(f"unknown state {state}")
    mission = row["mission"]
    s = graph.one("Q42", {"key": state}, read_only=True)
    elements = [Candidate(**e) for e in json.loads(s["elements"] or "[]")]
    forms = [e for e in elements if e.kind == "fill_submit"]
    if not forms:
        return {"ok": True, "mission": mission, "actions": [], "note": "page has no form"}
    words = set(text.lower().split())
    form = next((f for f in forms if words & set(f.target.replace("+", " ").split())), forms[0])
    values = load("inputs").get("mission_values", [])
    cases = [
        CaseIn(case=f"{mission.lower()}-{i + 1}", values={fid: v for fid in form.field_ids})
        for i, v in enumerate(values)
    ]
    from clew.explorer.perform import Account, render

    for c in cases:  # expand {{repeat:X:200}} now; credentials never appear in mission values
        c.values = {k: render(v, Account("", "")) for k, v in c.values.items()}
    rows = Tools(graph).cases_rows(state, [form.id], cases, "mission", 20)
    if isinstance(rows, str):
        raise OpError(rows)
    graph.run("Q04", {"state": state, "name": None, "actions": rows, "now": now_ms()})
    graph.run("Q27b", {"mission": mission, "keys": [r["key"] for r in rows]})
    graph.publish("mission", id=mission, state=state)
    return {"ok": True, "mission": mission, "actions": [r["key"] for r in rows]}
