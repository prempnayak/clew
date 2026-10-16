"""FalkorDB access: run named queries, publish events, copy and delete graphs.

`Graph.run("Q06", {...})` returns a list of dicts keyed by the RETURN aliases. Every run is also kept in a
short in-memory trace (query id, params, first rows) so the MCP audit and the UI can show the Cypher.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from clew.graph import queries

_EMBEDDED = None
_EMBEDDED_LOCK = threading.Lock()


def connect():
    """A FalkorDB connection from the environment. FALKORDB_EMBEDDED=1 uses falkordblite (tests, local dev)."""
    if os.environ.get("FALKORDB_EMBEDDED") == "1":
        return embedded()
    from falkordb import FalkorDB

    return FalkorDB(
        host=os.environ.get("FALKORDB_HOST", "localhost"),
        port=int(os.environ.get("FALKORDB_PORT", "6379")),
        password=os.environ.get("FALKORDB_PASSWORD") or None,
    )


def embedded():
    """One embedded FalkorDB per process (falkordblite)."""
    global _EMBEDDED
    with _EMBEDDED_LOCK:
        if _EMBEDDED is None:
            from redislite.falkordb_client import FalkorDB

            _EMBEDDED = FalkorDB(os.environ.get("FALKORDB_EMBEDDED_FILE") or None)
        return _EMBEDDED


def _value(v: Any) -> Any:
    """Turn FalkorDB result values (nodes, edges, paths) into plain Python."""
    if hasattr(v, "properties") and hasattr(v, "labels"):
        return dict(v.properties)
    if hasattr(v, "properties") and hasattr(v, "relation"):
        return dict(v.properties)
    if isinstance(v, list):
        return [_value(x) for x in v]
    if isinstance(v, dict):
        return {k: _value(x) for k, x in v.items()}
    return v


@dataclass
class Trace:
    qid: str
    params: dict
    rows: list[dict]
    ms: int
    seq: int = 0
    at: float = field(default_factory=time.time)


class Graph:
    """One named graph (one environment: nebula_live, iso_explorer-1, test_<uuid>, …)."""

    def __init__(self, db, name: str):
        self.db = db
        self.name = name
        self._g = db.select_graph(name)
        self.traces: list[Trace] = []
        self.seq = 0  # increases with every query; callers use it to find the traces since a point in time

    # -- queries -------------------------------------------------------------------------------------------
    def run(self, qid: str, params: dict | None = None, read_only: bool = False) -> list[dict]:
        q = queries.get(qid)
        params = params or {}
        started = time.time()
        rows: list[dict] = []
        for stmt in q.statements:
            res = self._g.ro_query(stmt, params) if read_only else self._g.query(stmt, params)
            header = [h[1] if isinstance(h, (list, tuple)) else h for h in (res.header or [])]
            header = [h.decode() if isinstance(h, bytes) else h for h in header]
            rows = [dict(zip(header, (_value(v) for v in row), strict=False)) for row in res.result_set]
        ms = int((time.time() - started) * 1000)
        self.seq += 1
        self.traces.append(Trace(qid, params, rows[:5], ms, self.seq))
        del self.traces[:-50]
        return rows

    def one(self, qid: str, params: dict | None = None, read_only: bool = False) -> dict | None:
        rows = self.run(qid, params, read_only)
        return rows[0] if rows else None

    def schema(self) -> None:
        """Q01, one statement per call; "already indexed" errors are ignored."""
        for stmt in queries.get("Q01").statements:
            try:
                self._g.query(stmt)
            except Exception as e:  # noqa: BLE001 - FalkorDB raises a generic ResponseError
                if "already indexed" not in str(e).lower():
                    raise

    # -- graph-level commands --------------------------------------------------------------------------------
    def exists(self) -> bool:
        return self.name in self.db.list_graphs()

    def delete(self) -> None:
        if self.exists():
            self._g.delete()

    def copy_to(self, dest: str) -> None:
        """GRAPH.COPY self -> dest (dest must not exist)."""
        self._g.copy(dest)

    def publish(self, event: str, **data: Any) -> None:
        """Wake-ups for workers and the UI: `clew:<graph>:events` on the FalkorDB server (Redis underneath)."""
        try:
            self.db.connection.publish(f"clew:{self.name}:events", json.dumps({"event": event, **data}))
        except Exception:  # noqa: BLE001 - events are best effort; workers poll as a fallback
            pass

    def incr(self, key: str) -> int:
        """A Redis counter outside the graph (explorer names survive graph resets)."""
        return int(self.db.connection.incr(f"clew:{self.name}:{key}"))


def open_graph(name: str | None = None, db=None) -> Graph:
    from clew.common.config import graph_name

    return Graph(db or connect(), name or graph_name())


def reset_from(db, source: str, dest: str) -> Graph:
    """GRAPH.DELETE dest, then GRAPH.COPY source dest (a fresh map from the seed or a snapshot)."""
    target = Graph(db, dest)
    target.delete()
    Graph(db, source).copy_to(dest)
    return Graph(db, dest)
