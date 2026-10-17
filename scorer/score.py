"""The scorer (handoff §20): the only code that reads the hidden answer key (shop/planted_bugs.yaml).

It compares the bugs Clew reported (filed or fixed) with the planted bugs and decoys, measures coverage of the
store's route patterns against /__routes, and reads duplicate executions (Q32) for the session.

    uv run python -m scorer.score [--graph nebula_live] [--session S-3] [--json out.json]

Run on the host: it reads .env and talks to FalkorDB and the store through the dev ports.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]
ANSWER_KEY = ROOT / "shop" / "planted_bugs.yaml"
REPORTED = {"filed", "fixed"}


def host_env() -> None:
    """Load .env and point container hostnames at the localhost dev ports."""
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    if os.environ.get("FALKORDB_HOST", "localhost") == "falkordb":
        os.environ["FALKORDB_HOST"] = "localhost"
        os.environ["FALKORDB_PORT"] = os.environ.get("FALKORDB_DEV_PORT", "6379")
    if "://shop:" in os.environ.get("SHOP_URL", ""):
        os.environ["SHOP_URL"] = f"http://localhost:{os.environ.get('SHOP_DEV_PORT', '8090')}"


def score(graph, routes: dict[str, list[str]] | None, session: dict | None) -> dict:
    key = yaml.safe_load(ANSWER_KEY.read_text())
    bugs = graph.run("Q33", read_only=True)
    releases = sorted({b["release_found"] for b in bugs if b["release_found"]} | {"v1"})
    started = session["started_at"] if session else min((b["first_seen"] for b in bugs), default=0)
    reported = [b for b in bugs if b["status"] in REPORTED]
    matched: set[str] = set()
    planted = []
    for p in key["bugs"]:
        if not set(p["releases"]) & set(releases):
            continue
        hits = [b for b in bugs if re.search(p["signature"], b["sig"])]
        rep = [b for b in hits if b["status"] in REPORTED]
        matched |= {b["sig"] for b in hits}
        first = min((b["first_seen"] for b in hits), default=None)
        planted.append(
            {
                "id": p["id"],
                "title": p["title"],
                "found": bool(hits),
                "reported": bool(rep),
                "issues": sorted({b["issue"] for b in rep if b["issue"]}),
                "status": [b["status"] for b in hits],
                "time_to_find_s": round((first - started) / 1000, 1) if first and started else None,
                "duplicate_reports": max(0, len(rep) - 1),
            }
        )
    decoys = [
        {"id": d["id"], "reported": [b["sig"] for b in reported if re.search(d["signature"], b["sig"], re.I)]}
        for d in key.get("decoys", [])
    ]
    others = [
        {"sig": b["sig"], "title": b["title"], "status": b["status"]} for b in reported if b["sig"] not in matched
    ]
    coverage = None
    if routes:
        expected = sorted(set().union(*(set(routes.get(r, [])) for r in releases)))
        seen = {r["route"] for r in graph.run("Q52", read_only=True)}
        coverage = {
            "expected": len(expected),
            "covered": len([r for r in expected if r in seen]),
            "missing": [r for r in expected if r not in seen],
        }
    dups = len(graph.run("Q32", {"session": session["id"]}, read_only=True)) if session else None
    found = [p for p in planted if p["reported"]]
    return {
        "graph": graph.name,
        "session": session["id"] if session else None,
        "releases": releases,
        "recall": f"{len(found)}/{len(planted)}",
        "planted": planted,
        "decoys_reported": sum(len(d["reported"]) for d in decoys),
        "decoys": decoys,
        "other_reported": others,
        "coverage": coverage,
        "duplicate_executions": dups,
        "at": int(time.time()),
    }


def markdown(s: dict) -> str:
    lines = [
        f"## Score: {s['graph']} {s['session'] or ''} (releases {', '.join(s['releases'])})",
        "",
        f"Recall **{s['recall']}** · decoys reported **{s['decoys_reported']}** · other reported bugs "
        f"**{len(s['other_reported'])}** · duplicate executions **{s['duplicate_executions']}**",
        "",
    ]
    if s["coverage"]:
        c = s["coverage"]
        lines.append(
            f"Route coverage **{c['covered']}/{c['expected']}**"
            + (f" (missing: {', '.join(c['missing'])})" if c["missing"] else "")
        )
        lines.append("")
    lines += ["| Bug | Reported | Issues | Time to find (s) | Status |", "|---|---|---|---|---|"]
    for p in s["planted"]:
        lines.append(
            f"| {p['id']} {p['title']} | {'✅' if p['reported'] else ('found' if p['found'] else '❌')} | "
            f"{', '.join(f'#{i}' for i in p['issues'])} | {p['time_to_find_s'] or ''} | "
            f"{', '.join(p['status'])} |"
        )
    for o in s["other_reported"]:
        lines.append(f"| other: {o['title']} | {o['status']} | | | `{o['sig']}` |")
    return "\n".join(lines)


def main() -> None:
    host_env()
    from clew.graph.client import Graph, connect

    p = argparse.ArgumentParser()
    p.add_argument("--graph", default=os.environ.get("CLEW_GRAPH", "nebula_live"))
    p.add_argument("--session", default=None)
    p.add_argument("--json", default=None)
    a = p.parse_args()
    g = Graph(connect(), a.graph)
    sessions = g.run("Q46", read_only=True)
    session = (
        next((s for s in sessions if s["id"] == a.session), None) if a.session else (sessions[0] if sessions else None)
    )
    routes = None
    try:
        r = httpx.get(
            f"{os.environ.get('SHOP_URL', 'http://localhost:8090')}/__routes",
            timeout=5,
            headers={"Authorization": f"Bearer {os.environ.get('SHOP_ADMIN_TOKEN', '')}"},
        )
        routes = r.json() if r.status_code == 200 else None
    except httpx.HTTPError:
        pass
    s = score(g, routes, session)
    out = Path(a.json) if a.json else ROOT / "eval" / "results" / f"score-{a.graph}-{s['session'] or 'none'}.json"
    out.write_text(json.dumps(s, indent=1, default=str))
    print(markdown(s))
    print(f"\nwritten to {out}")


if __name__ == "__main__":
    main()
