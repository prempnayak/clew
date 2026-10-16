"""Turn observed browser events and rule failures into problems (handoff §12.1).

Hard failures (pageerror, 5xx, crash, rule violations) are `new` bugs; console errors are `suspect`.
During replay work every problem is a `suspect`: replays exist to diff releases, and the regression pipeline
decides what changed (docs/decisions.md).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from clew.common.config import load
from clew.explorer.fingerprint import route_key
from clew.oracles import signatures
from clew.oracles.checks import Values, run_checks


@dataclass
class Event:
    kind: str  # pageerror | console_error | http_5xx | requestfailed | crash | nav_timeout
    message: str
    url: str = ""
    method: str = ""
    status: int = 0


@dataclass
class Problem:
    sig: str
    kind: str
    title: str
    status: str  # new | suspect
    message: str
    details: dict = field(default_factory=dict)


def _ignored(ev: Event, cfg: dict) -> bool:
    for rule in cfg.get("ignore", []):
        kind = rule.get("kind")
        if kind == ev.kind and rule.get("pattern") and re.search(rule["pattern"], ev.message):
            return True
        if kind == "response" and rule.get("url_pattern") and re.search(rule["url_pattern"], ev.url):
            return True
    return False


def problems_from(events: list[Event], page_route: str, state_key: str, action_key: str,
                  values: Values | None = None) -> list[Problem]:
    cfg = load("oracles")
    out: dict[str, Problem] = {}
    for ev in events:
        if _ignored(ev, cfg):
            continue
        if ev.kind == "http_5xx":
            route = route_key(ev.url)
            sig = signatures.http_5xx(ev.method, route, ev.status)
            out.setdefault(sig, Problem(sig, "http_5xx", f"{ev.method} {route} returns HTTP {ev.status}", "new",
                                        f"{ev.method} {ev.url} → {ev.status}", {"url": ev.url}))
        elif ev.kind == "pageerror":
            sig = signatures.pageerror(page_route, ev.message)
            out.setdefault(sig, Problem(sig, "pageerror", f"Uncaught {ev.message.split(':')[0]} on {page_route}", "new",
                                        ev.message))
        elif ev.kind == "crash":
            sig = f"crash|{page_route}"
            out.setdefault(sig, Problem(sig, "crash", f"Page crashed on {page_route}", "new", ev.message))
        elif ev.kind == "nav_timeout":
            sig = signatures.nav_timeout(state_key, action_key)
            out.setdefault(sig, Problem(sig, "nav_timeout", "Action timed out", "suspect", ev.message))
        elif ev.kind == "console_error":
            sig = signatures.console_error(page_route, ev.message)
            status = "suspect" if cfg.get("console_error", {}).get("as", "suspect") == "suspect" else "new"
            out.setdefault(sig, Problem(sig, "console_error", f"Console error on {page_route}", status, ev.message))
    for rule_id, msg in run_checks(page_route, values or {}, load("checks")):
        sig = signatures.rule(rule_id, state_key)
        out.setdefault(sig, Problem(sig, "rule", f"Rule {rule_id} fails on {page_route}", "new", msg,
                                    {"rule": rule_id, "values": values}))
    return list(out.values())


def severity(problem: Problem, importance_percentile: float) -> str:
    """P1: wrong money or data, or a crash/5xx on a top-quarter page. P2: other crashes, regressions. P3: rest."""
    cfg = load("oracles").get("severity", {})
    if problem.kind == "rule" and problem.details.get("rule") in cfg.get("p1_rules", []):
        return "P1"
    if problem.kind in ("http_5xx", "pageerror", "crash"):
        return "P1" if importance_percentile >= cfg.get("p1_importance_percentile", 0.75) else "P2"
    if problem.kind == "regression":
        return "P2"
    return "P3"
