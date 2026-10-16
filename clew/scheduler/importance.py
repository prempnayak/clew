"""Page importance: betweenness centrality over the state graph (Q09), with a fixed sampling seed."""

from __future__ import annotations

from clew.graph.client import Graph


def recompute(graph: Graph) -> int:
    """Q09. Returns the number of states scored (0 while the map has no transitions yet)."""
    try:
        row = graph.one("Q09")
    except Exception as e:  # noqa: BLE001
        if "unknown relationship-type" in str(e) or "unknown label" in str(e).lower():
            return 0  # an empty map has no HAS_ACTION/LEADS_TO edges yet
        raise
    states = row["states"] if row else 0
    graph.publish("importance", states=states)
    return states
