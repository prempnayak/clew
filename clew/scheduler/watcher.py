"""Release watcher and scheduler.

- Every few seconds: GET /__version. On a change: Q16 (new release), then replay jobs (Q17) and verify_fix
  jobs (Q18). When the release's replay jobs have drained: the regression pipeline (Q19 → Q35, Q12, Q20).
- On startup: Q17 and Q18 again for the current release; both skip work already queued or done, so a restart
  between Q16 and Q17 can't lose or duplicate jobs.
- Every minute: importance (Q09) and coverage (Q23), published for the UI.

Run: python -m clew.scheduler.watcher
"""

from __future__ import annotations

import time

import httpx

from clew.common.config import load, shop_url
from clew.common.ids import now_ms
from clew.common.log import get, kv
from clew.graph.client import Graph, open_graph
from clew.scheduler import importance, regressions

log = get("watcher")


class Watcher:
    def __init__(self, graph: Graph, base_url: str | None = None):
        self.graph = graph
        self.base_url = (base_url or shop_url()).rstrip("/")
        self.last_importance = 0.0

    def store_release(self) -> str | None:
        try:
            return httpx.get(f"{self.base_url}/__version", timeout=5).json()["release"]
        except Exception:  # noqa: BLE001 - the store may be restarting
            return None

    def enqueue(self, previous: str, release: str) -> None:
        now = now_ms()
        replays = self.graph.one("Q17", {"previous": previous, "release": release, "now": now})["queued"]
        fixes = self.graph.one("Q18", {"release": release, "now": now})["queued"]
        if replays or fixes:
            self.graph.publish("job.updated", kind="replay", queued=replays, verify_fix=fixes)
            log.info(kv(release=release, replay_jobs=replays, verify_fix_jobs=fixes))

    def tick(self) -> None:
        current = self.graph.one("Q37", read_only=True)
        live = self.store_release()
        if current and live and live != current["release"]:
            row = self.graph.one("Q16", {"release": live, "now": now_ms()})
            if row:
                log.info(kv(new_release=row["current"], previous=row["previous"]))
                self.graph.publish("release.changed", previous=row["previous"], current=row["current"])
                self.enqueue(row["previous"], row["current"])
        prev = self.graph.one("Q49", read_only=True)
        if prev:
            pending = self.graph.one("Q39", {"kind": "replay", "release": prev["current"]}, read_only=True)
            if pending and pending["pending"] == 0:
                regressions.process(self.graph, prev["previous"], prev["current"])
        if time.time() - self.last_importance >= load("session").get("importance_every_s", 60):
            importance.recompute(self.graph)
            self.graph.publish("coverage", **self.graph.one("Q23", read_only=True))
            self.last_importance = time.time()

    def run(self) -> None:
        prev = self.graph.one("Q49", read_only=True)
        if prev:
            self.enqueue(prev["previous"], prev["current"])
        poll = load("session").get("version_poll_s", 5)
        while True:
            self.graph.run(
                "Q28",
                {
                    "name": "release-watcher",
                    "role": "scheduler",
                    "model": "none",
                    "session": None,
                    "state": "running",
                    "work": None,
                    "now": now_ms(),
                },
            )
            try:
                self.tick()
            except Exception as e:  # noqa: BLE001 - keep watching
                log.exception(kv(error=str(e)))
            time.sleep(poll)


def main() -> None:
    Watcher(open_graph()).run()


if __name__ == "__main__":
    main()
