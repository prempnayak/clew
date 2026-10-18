"""War-room API (handoff §15.3): map, bugs, swarm, release diff, Show Cypher, SSE, session controls.
Every read is a named query; the API also serves the built UI from ui/dist.

Run: uvicorn clew.api.app:app --port 8081
"""

from __future__ import annotations

import asyncio
import json
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from clew.api import ops
from clew.common.config import ROOT, env
from clew.common.log import get
from clew.graph import queries
from clew.graph.client import Graph, open_graph
from clew.mcp_server.tools import Tools

log = get("api")
_graph: Graph | None = None


def graph() -> Graph:
    global _graph
    if _graph is None:
        _graph = open_graph()
    return _graph


async def session_timer() -> None:
    while True:
        try:
            await asyncio.to_thread(ops.expire_sessions, graph())
        except Exception as e:  # noqa: BLE001
            log.warning("session timer: %s", e)
        await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(session_timer())
    yield
    task.cancel()


app = FastAPI(title="Clew", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
HOSTED = env("HOSTED_MODE", "false").lower() == "true"


def q(qid: str, params: dict | None = None) -> list[dict]:
    return graph().run(qid, params or {}, read_only=True)


@app.exception_handler(ops.OpError)
async def op_error(_req: Request, exc: ops.OpError):
    return JSONResponse({"ok": False, "error": str(exc)}, status_code=409)


# -- reads --------------------------------------------------------------------------------------------------------
@app.get("/api/overview")
def overview() -> dict:
    rel = graph().one("Q37", read_only=True)
    prev = graph().one("Q49", read_only=True)
    return {
        "graph": graph().name,
        "release": rel["release"] if rel else None,
        "previous": prev["previous"] if prev else None,
        "session": ops.running_session(graph()),
        "coverage": graph().one("Q23", read_only=True),
        "hosted": HOSTED,
        "filing": env("GITHUB_FILING", "dry_run"),
        "store_url": env("CLEW_STORE_PUBLIC_URL"),
        "llm": env("LLM_BACKEND", "off"),
    }


@app.get("/api/map")
def map_view() -> dict:
    rel = graph().one("Q37", read_only=True)
    prev = graph().one("Q49", read_only=True)
    edges = [e | {"release": rel["release"]} for e in q("Q30", {"release": rel["release"]})] if rel else []
    if prev:
        seen = {(e["source"], e["action_key"]) for e in edges}
        edges += [
            e | {"release": prev["previous"], "stale": True}
            for e in q("Q30", {"release": prev["previous"]})
            if (e["source"], e["action_key"]) not in seen
        ]
    return {"states": q("Q47"), "edges": edges}


@app.get("/api/states/{key:path}")
def state(key: str) -> dict:
    s = graph().one("Q42", {"key": key}, read_only=True)
    if not s:
        raise HTTPException(404)
    s["elements"] = json.loads(s["elements"] or "[]")
    s["actions"] = sorted([a for a in s["actions"] if a.get("key")], key=lambda a: -(a.get("priority") or 0))
    return s


@app.get("/api/bugs")
def bugs() -> list[dict]:
    return q("Q33")


@app.get("/api/bugs/{sig:path}")
def bug(sig: str) -> dict:
    b = graph().one("Q38", {"sig": sig}, read_only=True)
    if not b:
        raise HTTPException(404)
    b["evidence"] = json.loads(b["evidence"] or "{}")
    r = Tools(graph()).repro(sig)
    b["repro"] = r.model_dump() if r else None
    return b


@app.get("/api/coverage")
def coverage() -> dict:
    return graph().one("Q23", read_only=True)


@app.get("/api/agents")
def agents() -> list[dict]:
    return q("Q43")


@app.get("/api/jobs")
def jobs(limit: int = 50) -> list[dict]:
    return q("Q45", {"limit": min(limit, 500)})


@app.get("/api/sessions")
def sessions() -> list[dict]:
    rows = q("Q46")
    for r in rows:
        r["summary"] = json.loads(r["summary"]) if r.get("summary") else None
        r["llm"] = q("Q31", {"session": r["id"]})
        r["duplicates"] = len(q("Q32", {"session": r["id"]}))
        r["stats"] = graph().one("Q51", {"session": r["id"]}, read_only=True)
    return rows


@app.get("/api/missions")
def missions() -> list[dict]:
    return q("Q50")


@app.get("/api/facts")
def facts(limit: int = 30) -> list[dict]:
    return q("Q26", {"kinds": ["precondition", "input", "rename", "note"], "limit": min(limit, 200)})


@app.get("/api/timeline")
def timeline(limit: int = 50) -> list[dict]:
    return q("Q55", {"limit": min(limit, 500)})


@app.get("/api/growth")
def growth() -> list[dict]:
    return sorted(q("Q53"), key=lambda r: r["at"] or 0)


@app.get("/api/diff")
def diff(previous: str | None = None, current: str | None = None) -> dict:
    if not previous or not current:
        prev = graph().one("Q49", read_only=True)
        if not prev:
            return {"previous": None, "current": None, "regressions": [], "variants": [], "changes": None}
        previous, current = prev["previous"], prev["current"]
    rows = q("Q19", {"previous": previous, "release": current})
    return {
        "previous": previous,
        "current": current,
        "regressions": [r for r in rows if r["change"] != "variant"],  # broken or moved: filed as bugs
        "variants": [r for r in rows if r["change"] == "variant"],  # same page, other layout or data: not filed
        "changes": graph().one("Q54", {"release": current}, read_only=True),
        "replays_pending": graph().one("Q39", {"kind": "replay", "release": current}, read_only=True),
    }


@app.get("/api/toolcalls")
def toolcalls(limit: int = 30) -> list[dict]:
    return q("Q44", {"limit": min(limit, 200)})


@app.get("/api/toolcalls/{tid}")
def toolcall(tid: str) -> dict:
    t = graph().one("Q44b", {"id": tid}, read_only=True)
    if not t:
        raise HTTPException(404)
    t["trace"] = json.loads(t.get("trace") or "[]")
    for step in t["trace"]:
        step["cypher"] = queries.get(step["qid"]).text
    return t


@app.get("/api/queries")
def query_list() -> list[dict]:
    return [{"id": x.id, "name": x.name, "purpose": x.purpose} for x in queries.all_queries().values()]


@app.get("/api/queries/{qid}")
def query(qid: str) -> dict:
    try:
        x = queries.get(qid)
    except KeyError:
        raise HTTPException(404) from None
    return {
        "id": x.id,
        "name": x.name,
        "purpose": x.purpose,
        "params": x.params,
        "callers": x.callers,
        "cypher": x.text,
    }


@app.get("/api/screenshots/{name}")
def screenshot(name: str):
    if not re.fullmatch(r"[0-9a-f]{12}\.png", name):
        raise HTTPException(404)
    path = Path(env("CLEW_SCREENSHOTS", "artifacts/screenshots")) / name
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path)


@app.get("/api/stream")
async def stream(request: Request):
    """Server-sent events relayed from the graph's pub/sub channel `clew:<graph>:events`."""
    import redis.asyncio as aioredis

    async def events():
        r = aioredis.Redis(
            host=env("FALKORDB_HOST", "localhost"),
            port=int(env("FALKORDB_PORT", "6379")),
            password=env("FALKORDB_PASSWORD") or None,
        )
        ps = r.pubsub()
        await ps.subscribe(f"clew:{graph().name}:events")
        try:
            while not await request.is_disconnected():
                msg = await ps.get_message(ignore_subscribe_messages=True, timeout=15)
                if msg is None:
                    yield {"event": "ping", "data": "{}"}
                    continue
                data = msg["data"].decode() if isinstance(msg["data"], bytes) else msg["data"]
                yield {"event": json.loads(data).get("event", "message"), "data": data}
        finally:
            await ps.unsubscribe()
            await r.aclose()

    return EventSourceResponse(events())


# -- controls -----------------------------------------------------------------------------------------------------
class SessionIn(BaseModel):
    explorers: int = Field(default=4, ge=1, le=8)
    minutes: float = Field(default=10, gt=0, le=60)
    mode: str = "shared"
    start_from: str = "fresh"


class ReleaseIn(BaseModel):
    release: str = Field(pattern=r"^v[12]$")


class MissionIn(BaseModel):
    state: str
    text: str = Field(min_length=3, max_length=300)


@app.post("/api/sessions")
def start(req: SessionIn) -> dict:
    return ops.start_session(graph(), req.explorers, req.minutes, req.mode, req.start_from)


@app.post("/api/sessions/{sid}/stop")
def stop(sid: str) -> dict:
    return ops.stop_session(graph(), sid)


@app.post("/api/explorers/kill")
def kill() -> dict:
    return ops.controller("/kill")


@app.post("/api/restart-all")
def restart_all() -> dict:
    if HOSTED:
        raise HTTPException(403, "disabled in hosted mode")
    return ops.controller("/restart")


@app.post("/api/release")
def release(req: ReleaseIn) -> dict:
    return {"ok": True, **ops.store_release(req.release)}


@app.post("/api/reset")
def reset() -> dict:
    if HOSTED and ops.running_session(graph()):
        raise HTTPException(409, "a session is running")
    return ops.reset_all(graph())


@app.post("/api/missions")
def mission(req: MissionIn) -> dict:
    return ops.add_mission(graph(), req.state, req.text)


# -- the built UI --------------------------------------------------------------------------------------------------
UI_DIST = Path(env("CLEW_UI_DIST", str(ROOT / "ui" / "dist")))
if UI_DIST.exists():
    app.mount("/assets", StaticFiles(directory=UI_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        return FileResponse(UI_DIST / "index.html")
