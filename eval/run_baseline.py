"""S5: the same session in two modes, several times each (handoff §5, §13.5).

- shared: the normal design, one map, claims and memory in one graph;
- isolated: each explorer gets a private copy of the seed (iso_<agent>): no shared claims, facts or routes.

Measures per run: actions executed, duplicate executions (the same action key run by more than one explorer),
unique actions, page reads, LLM calls, and time to each planted bug (first sighting, via the scorer).
Uses the API (sessions run in Docker) and reads the graphs directly. Results: eval/results/baseline.{json,md}.

    uv run python eval/run_baseline.py --runs 3 --minutes 10 --explorers 4
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scorer.score import host_env, score  # noqa: E402

RESULTS = ROOT / "eval" / "results"


def api_url() -> str:
    return os.environ.get("CLEW_API", f"http://localhost:{os.environ.get('API_DEV_PORT', '8081')}")


def run_once(db, mode: str, explorers: int, minutes: float) -> dict:
    from clew.graph.client import Graph

    live = Graph(db, os.environ.get("CLEW_GRAPH", "nebula_live"))
    r = httpx.post(
        f"{api_url()}/api/sessions",
        timeout=120,
        json={"explorers": explorers, "minutes": minutes, "mode": mode, "start_from": "fresh"},
    )
    r.raise_for_status()
    sid = r.json()["session"]
    print(f"[{mode}] session {sid} running for {minutes} min", flush=True)
    deadline = time.time() + minutes * 60 + 90
    while time.time() < deadline:
        s = next((x for x in live.run("Q46", read_only=True) if x["id"] == sid), None)
        if s and s["status"] == "ended":
            break
        time.sleep(10)
    else:
        httpx.post(f"{api_url()}/api/sessions/{sid}/stop", timeout=60)
    session = next(x for x in live.run("Q46", read_only=True) if x["id"] == sid)
    graphs = [live] if mode == "shared" else [Graph(db, n) for n in db.list_graphs() if n.startswith("iso_")]
    performed: dict[str, set[str]] = defaultdict(set)
    steps = reads = llm = 0
    first_seen: dict[str, float] = {}
    for g in graphs:
        for row in g.run("Q56", {"session": sid}, read_only=True):
            performed[row["action"]].add(row["agent"])
            steps += 1
        reads += int(g.one("Q57", read_only=True)["reads"] or 0)
        llm += int((g.one("Q51", {"session": sid}, read_only=True) or {}).get("llm_calls") or 0)
        for p in score(g, None, session)["planted"]:
            if p["time_to_find_s"] is not None:
                first_seen[p["id"]] = min(first_seen.get(p["id"], 1e9), p["time_to_find_s"])
    if mode == "isolated":
        for g in graphs:
            g.delete()
    dups = sum(1 for agents in performed.values() if len(agents) > 1)
    return {
        "mode": mode,
        "session": sid,
        "actions_executed": steps,
        "unique_actions": len(performed),
        "duplicate_actions": dups,
        "page_reads": reads,
        "llm_calls": llm,
        "time_to_bug_s": first_seen,
    }


def table(runs: list[dict]) -> str:
    bugs = sorted({b for r in runs for b in r["time_to_bug_s"]})
    lines = ["| Metric (median of runs) | shared | isolated |", "|---|---|---|"]

    def med(mode: str, f) -> str:
        vals = [f(r) for r in runs if r["mode"] == mode]
        vals = [v for v in vals if v is not None]
        return f"{statistics.median(vals):g}" if vals else "–"

    for key, label in [
        ("actions_executed", "Actions executed"),
        ("unique_actions", "Unique actions covered"),
        ("duplicate_actions", "Actions run by more than one explorer"),
        ("page_reads", "Page reads"),
        ("llm_calls", "LLM calls"),
    ]:
        lines.append(f"| {label} | {med('shared', lambda r, k=key: r[k])} | {med('isolated', lambda r, k=key: r[k])} |")
    for b in bugs:
        lines.append(
            f"| Time to {b} (s) | {med('shared', lambda r, b=b: r['time_to_bug_s'].get(b))} | "
            f"{med('isolated', lambda r, b=b: r['time_to_bug_s'].get(b))} |"
        )
    n = {m: sum(1 for r in runs if r["mode"] == m) for m in ("shared", "isolated")}
    lines.append(f"\nRuns: {n['shared']} shared, {n['isolated']} isolated. '–' = not found in any run.")
    return "\n".join(lines)


def main() -> None:
    host_env()
    from clew.graph.client import connect

    p = argparse.ArgumentParser()
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--minutes", type=float, default=10)
    p.add_argument("--explorers", type=int, default=4)
    p.add_argument("--modes", default="shared,isolated")
    a = p.parse_args()
    db = connect()
    runs = []
    for _ in range(a.runs):
        for mode in a.modes.split(","):
            runs.append(run_once(db, mode, a.explorers, a.minutes))
            print(json.dumps(runs[-1]), flush=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "baseline.json").write_text(json.dumps(runs, indent=1))
    md = table(runs)
    (RESULTS / "baseline.md").write_text(md + "\n")
    print(md)


if __name__ == "__main__":
    main()
