"""Routes over the map: weighted shortest path (Q10) turned into performable steps (Q10b)."""

from __future__ import annotations

import json
from dataclasses import dataclass

from clew.graph.client import Graph


@dataclass
class Step:
    key: str
    details: dict
    expected: str | None  # the state this step should reach

    @property
    def selector(self) -> dict:
        return json.loads(self.details.get("selector") or "{}")

    @property
    def inputs(self) -> dict:
        return json.loads(self.details.get("inputs") or "{}")


def details(graph: Graph, keys: list[str]) -> dict[str, dict]:
    return {r["key"]: r for r in graph.run("Q10b", {"keys": keys}, read_only=True)}


def steps_for(graph: Graph, keys: list[str], states: list[str]) -> list[Step]:
    """`states` are the states along the path; step i should reach states[i + 1]."""
    d = details(graph, keys)
    return [Step(k, d[k], states[i + 1] if i + 1 < len(states) else None) for i, k in enumerate(keys) if k in d]


def plan(graph: Graph, src: str, dst: str) -> list[Step] | None:
    """Steps from src to dst; [] when already there; None when unreachable (no route, or cost ≥ 1000)."""
    if src == dst:
        return []
    row = graph.one("Q10", {"from": src, "to": dst}, read_only=True)
    if not row or row["cost"] is None or row["cost"] >= 1000:
        return None
    return steps_for(graph, row["actions"], row["states"])
