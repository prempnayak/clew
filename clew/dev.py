"""Run the whole swarm in one process for local development and the integration test:
the release watcher, the Reporter and N explorers, all coordinating only through the graph.

    python -m clew.dev --explorers 2 --minutes 5

(Docker Compose runs each of these as its own container instead; the code paths are the same.)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import time

from clew.common.config import graph_name
from clew.explorer.worker import Explorer, account_for
from clew.graph.client import Graph, connect
from clew.reporter.runner import Reporter
from clew.scheduler.watcher import Watcher


async def run_swarm(graph: Graph, explorers: int, minutes: float, stop_when=None, base_url: str | None = None) -> None:
    from playwright.async_api import async_playwright

    deadline = time.time() + minutes * 60
    watcher = Watcher(graph, base_url)
    reporter = Reporter(graph)
    stop = asyncio.Event()

    async def background() -> None:
        last_tick = 0.0
        while not stop.is_set() and time.time() < deadline:
            if time.time() - last_tick > 3:
                try:
                    await asyncio.to_thread(watcher.tick)
                except Exception as e:  # noqa: BLE001 - keep going, like the real watcher
                    print("watcher error:", e)
                last_tick = time.time()
            while await reporter.run_once():
                pass
            if stop_when and stop_when(graph):
                stop.set()
            await asyncio.sleep(0.5)
        stop.set()

    async def explore(e: Explorer) -> None:
        while not stop.is_set() and time.time() < deadline:
            if not await e.step():
                await asyncio.sleep(0.5)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=os.environ.get("HEADED") != "1")
        workers = []
        for _ in range(explorers):
            n = graph.incr("explorers")
            workers.append(Explorer(graph, f"explorer-{n}", browser, account_for(n), base_url))
        await asyncio.gather(background(), *(explore(w) for w in workers))
        await browser.close()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--explorers", type=int, default=2)
    p.add_argument("--minutes", type=float, default=5)
    a = p.parse_args()
    asyncio.run(run_swarm(Graph(connect(), graph_name()), a.explorers, a.minutes))


if __name__ == "__main__":
    main()
