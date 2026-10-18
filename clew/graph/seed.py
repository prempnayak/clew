"""`make seed`: indexes + App + Release v1 into <app>_seed, then copy it to the live graph (Q01, Q02)."""

from __future__ import annotations

import argparse

from clew.common.config import app_name, env, seed_graph, shop_url
from clew.common.ids import now_ms
from clew.graph.client import Graph, connect, reset_from


def seed(db, live: str, release: str = "v1") -> Graph:
    g = Graph(db, seed_graph())
    g.delete()
    g.schema()
    g.run("Q02", {"app": app_name(), "base_url": shop_url(), "release": release, "now": now_ms()})
    return reset_from(db, seed_graph(), live)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--graph", default=env("CLEW_GRAPH", "nebula_live"))
    args = p.parse_args()
    seed(connect(), args.graph)
    print(f"seeded {seed_graph()} and copied it to {args.graph}")


if __name__ == "__main__":
    main()
