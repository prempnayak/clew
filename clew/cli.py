"""Command line for the Makefile (handoff Appendix F).

python -m clew.cli reset | session --explorers 4 --minutes 10 --mode shared --start fresh | stop
python -m clew.cli kill-explorer | restart-all | release v2 | snapshot nebula_v1_map
python -m clew.cli mission --state '/cart|in|…' --text 'Test invalid coupon codes'
python -m clew.cli replay --bug '<sig>' --headed
"""

from __future__ import annotations

import argparse
import asyncio
import json

from clew.api import ops
from clew.graph.client import open_graph


async def replay(sig: str, headed: bool) -> None:
    """Replay a bug's repro steps in a (visible) browser for a human. Records nothing."""
    from playwright.async_api import async_playwright

    from clew.explorer import route
    from clew.explorer.perform import perform, settle
    from clew.explorer.worker import account_for
    from clew.mcp_server.tools import Tools

    g = open_graph()
    r = Tools(g).repro(sig)
    if r is None:
        raise SystemExit(f"no known route to {sig}")
    print(r.text)
    bug = g.one("Q38", {"sig": sig}, read_only=True)
    instance = int((json.loads(bug["evidence"] or "{}").get("instance") or {}).get("index", 0))
    details = route.details(g, [s.action for s in r.steps if s.action])
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not headed, slow_mo=400 if headed else 0)
        page = await (await browser.new_context()).new_page()
        page.on("pageerror", lambda e: print("  pageerror:", e.name, e.message))
        page.on("response", lambda resp: resp.status >= 500 and print("  HTTP", resp.status, resp.url))
        from clew.common.config import shop_url

        await page.goto(shop_url() + "/")
        await settle(page, 3000)
        keys = [s.action for s in r.steps if s.action]
        for i, k in enumerate(keys):
            d = details[k]
            done = await perform(
                page,
                json.loads(d["selector"]),
                d["kind"],
                json.loads(d["inputs"] or "{}"),
                instance if i == len(keys) - 1 else 0,
                account_for(1),
            )
            print(f"  step {i + 2}: {'ok' if done.ok else done.error} → {page.url}")
        if headed:
            await page.wait_for_timeout(5000)
        await browser.close()


def main() -> None:
    p = argparse.ArgumentParser(prog="clew")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("reset")
    s = sub.add_parser("session")
    s.add_argument("--explorers", type=int, default=4)
    s.add_argument("--minutes", type=float, default=10)
    s.add_argument("--mode", default="shared")
    s.add_argument("--start", default="fresh")
    sub.add_parser("stop")
    sub.add_parser("kill-explorer")
    sub.add_parser("restart-all")
    r = sub.add_parser("release")
    r.add_argument("release")
    sn = sub.add_parser("snapshot")
    sn.add_argument("name", nargs="?", default=None)
    m = sub.add_parser("mission")
    m.add_argument("--state", required=True)
    m.add_argument("--text", required=True)
    rp = sub.add_parser("replay")
    rp.add_argument("--bug", required=True)
    rp.add_argument("--headed", action="store_true")
    a = p.parse_args()

    g = open_graph()
    if a.cmd == "reset":
        out = ops.reset_all(g)
    elif a.cmd == "session":
        out = ops.start_session(g, a.explorers, a.minutes, a.mode, a.start)
    elif a.cmd == "stop":
        out = ops.stop_session(g)
    elif a.cmd == "kill-explorer":
        out = ops.controller("/kill")
    elif a.cmd == "restart-all":
        out = ops.controller("/restart")
    elif a.cmd == "release":
        out = ops.store_release(a.release)
    elif a.cmd == "snapshot":
        out = ops.snapshot(g, a.name)
    elif a.cmd == "mission":
        out = ops.add_mission(g, a.state, a.text)
    else:
        asyncio.run(replay(a.bug, a.headed))
        return
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
