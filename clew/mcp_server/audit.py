"""Audit trail: every tool call writes a ToolCall node (Q29) with the queries it ran, their parameters and first
rows (Show Cypher), linked to the bug it was about (Q29b)."""

from __future__ import annotations

import functools
import json
import time
from collections.abc import Callable
from typing import Any

from clew.common.ids import now_ms, short_id


def audited(fn: Callable[..., dict]) -> Callable[..., dict]:
    """Wrap a Tools method: catch errors as {"ok": false}, time it, record the ToolCall. Keeps the signature."""

    @functools.wraps(fn)
    def wrapper(self, *args: Any, agent: str, **kwargs: Any) -> dict:
        graph = self.graph
        mark = graph.seq
        started = time.time()
        try:
            result = fn(self, *args, agent=agent, **kwargs)
        except Exception as e:  # noqa: BLE001 - tools never raise to the model
            result = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        ms = int((time.time() - started) * 1000)
        traces = [t for t in graph.traces if t.seq > mark]
        tool_id = short_id("T")
        summary = result.get("error") if not result.get("ok", True) else result.get("summary", "ok")
        graph.run(
            "Q29",
            {
                "id": tool_id,
                "tool": fn.__name__,
                "agent": agent,
                "args": json.dumps(kwargs | {"args": list(args)}, default=str)[:4000],
                "query_ids": [t.qid for t in traces],
                "trace": json.dumps(
                    [{"qid": t.qid, "params": t.params, "rows": t.rows[:3], "ms": t.ms} for t in traces], default=str
                )[:20000],
                "ms": ms,
                "ok": bool(result.get("ok", True)),
                "summary": str(summary)[:300],
                "now": now_ms(),
            },
        )
        sig = kwargs.get("sig") or (args[0] if args and isinstance(args[0], str) and "|" in args[0] else None)
        if sig:
            graph.run("Q29b", {"id": tool_id, "sig": sig})
        graph.publish("toolcall", id=tool_id, tool=fn.__name__, agent=agent, ok=bool(result.get("ok", True)))
        result["tool_call"] = tool_id
        return result

    return wrapper
