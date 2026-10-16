"""Integration (handoff §20): one explorer with the deterministic page reader, the Reporter and the release
watcher against the real store must find, confirm and file B2, B3 and B1, with no LLM.

Slow (a few minutes) and needs Chromium: `uv run pytest -m integration`.
"""

from __future__ import annotations

import asyncio
import os
import socket
import threading
import time
import uuid

import pytest

pytestmark = pytest.mark.integration

WANTED = ["http_5xx|GET /checkout|500", "pageerror|/wishlist|", "rule|coupon_max_10pct|/cart"]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    os.environ["SHOP_DB"] = str(tmp_path_factory.mktemp("shop") / "nebula.db")
    os.environ["SHOP_EXPLORER_PASSWORD"] = "pw"
    os.environ["SHOP_ADMIN_TOKEN"] = "it-token"
    import importlib

    import uvicorn

    from shop import app as app_mod
    from shop import db

    importlib.reload(db)
    importlib.reload(app_mod)
    db.reset()
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(app_mod.app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True


def test_one_explorer_finds_b2_b3_b1(store, db, monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "off")
    monkeypatch.setenv("GITHUB_FILING", "dry_run")
    monkeypatch.setenv("SHOP_URL", store)
    from clew.dev import run_swarm
    from clew.graph.client import Graph

    g = Graph(db, f"test_{uuid.uuid4().hex[:8]}")
    g.schema()
    g.run("Q02", {"app": "nebula-gear", "base_url": store, "release": "v1", "now": 1})

    def filed(graph) -> list[str]:
        sigs = [b["sig"] for b in graph.run("Q33") if b["status"] == "filed"]
        return [w for w in WANTED if any(s.startswith(w) for s in sigs)]

    try:
        asyncio.run(run_swarm(g, explorers=1, minutes=8, stop_when=lambda gr: len(filed(gr)) == 3, base_url=store))
        assert filed(g) == WANTED
        bugs = g.run("Q33")
        assert not [
            b
            for b in bugs
            if b["status"] == "filed" and not any(b["sig"].startswith(w) for w in WANTED + ["rule|price_is_number"])
        ]
        for w in WANTED:
            sig = next(b["sig"] for b in bugs if b["sig"].startswith(w))
            assert g.one("Q38", {"sig": sig})["issue_body"].count("**Steps to reproduce**") == 1
    finally:
        g.delete()
