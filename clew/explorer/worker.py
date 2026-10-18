"""The explorer worker: claim work from the graph, walk the shortest known route to it, act,
observe, record. It keeps no work state between items: everything it knows comes from FalkorDB.

Every work item starts in a fresh, logged-out browser context at the entry page, so a route always replays from
scratch and the map's edges mean the same thing for every explorer.

Run one explorer:          python -m clew.explorer.worker
Run several in-process:     python -m clew.explorer.worker --count 4 --minutes 10
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from clew.common.config import env, graph_name, lease_ms, load, seed_graph, shop_url
from clew.common.ids import now_ms, short_id
from clew.common.log import get, kv
from clew.explorer import locate as locate_mod
from clew.explorer import page_reader, route
from clew.explorer.extract import Candidate, extract, messages, normalize
from clew.explorer.fingerprint import default_name, fingerprint
from clew.explorer.observe import Observer
from clew.explorer.perform import Account, Performed, perform, settle, snapshots, testid_values
from clew.graph.client import Graph, connect, reset_from
from clew.oracles.detectors import Event, Problem, problems_from, severity

log = get("explorer")


@dataclass
class Work:
    kind: str  # explore | mission | variation | confirm | replay | verify_fix
    target: str  # action key or bug signature
    state: str | None = None
    instance: int = 0
    job_id: str | None = None
    payload: dict = field(default_factory=dict)


@dataclass
class Arrival:
    key: str
    route: str
    url: str
    page_snap: str
    main_snap: str
    candidates: list[Candidate]
    path: list[str] = field(default_factory=list)  # action keys walked from the entry page in this context
    states: list[str] = field(default_factory=list)  # states along that path, ending with this one


@dataclass
class Outcome:
    arrival: Arrival | None
    performed: Performed
    problems: list[Problem]
    ok: bool
    ms: int


class Explorer:
    def __init__(self, graph: Graph, name: str, browser, account: Account, base_url: str | None = None):
        self.graph = graph
        self.name = name
        self.browser = browser
        self.account = account
        self.base_url = (base_url or shop_url()).rstrip("/")
        self.run_id: str | None = None
        self.session = "S-0"
        self.release = "v1"
        self.pending_llm = 0
        self.work: Work | None = None  # the item being worked on right now (never kept between items)
        self.screens = Path(env("CLEW_SCREENSHOTS", "artifacts/screenshots"))

    # -- claims ---------------------------------------------------------------------------------------------------
    def claim(self) -> Work | None:
        now = now_ms()
        j = self.graph.one("Q05", {"agent": self.name, "now": now, "lease_ms": lease_ms("job")})
        if j:
            return Work(j["kind"], j["target"], job_id=j["id"], payload=json.loads(j["payload"] or "{}"))
        a = self.graph.one("Q06", {"agent": self.name, "now": now, "lease_ms": lease_ms("action")})
        if a:
            kind = "mission" if a["origin"] == "mission" else "explore"
            return Work(kind, a["action"], state=a["state"])
        v = self.graph.one("Q06b", {"agent": self.name, "now": now, "lease_ms": lease_ms("action")})
        if v:
            return Work("variation", v["action"], state=v["state"], instance=int(v["instance"] or 0))
        return None

    def heartbeat(self, state: str, work: str | None = None) -> None:
        self.graph.run(
            "Q28",
            {
                "name": self.name,
                "role": "explorer",
                "model": "page_reader",
                "session": self.session,
                "state": state,
                "work": work,
                "now": now_ms(),
            },
        )
        self.graph.publish("agent.heartbeat", agent=self.name, state=state, work=work)

    def refresh_context(self) -> None:
        rel = self.graph.one("Q37", read_only=True)
        self.release = rel["release"] if rel else "v1"
        running = [s for s in self.graph.run("Q46", read_only=True) if s["status"] == "running"]
        self.session = env("CLEW_SESSION") or (running[0]["id"] if running else "S-0")
        if self.run_id is None:
            self.run_id = f"RUN-{self.graph.one('Q41', {'name': 'run'})['v']}"

    # -- one work item -------------------------------------------------------------------------------------------
    async def step(self) -> bool:
        """Claim and do one work item. False when there was nothing to do."""
        self.refresh_context()
        work = self.claim()
        if work is None:
            if self.graph.one("Q40", read_only=True) is None:
                await self.bootstrap()
                return True
            self.heartbeat("idle")
            return False
        self.work = work
        self.heartbeat("working", f"{work.kind}:{work.target}")
        self.graph.publish("claim", agent=self.name, kind=work.kind, target=work.target)
        log.info(kv(agent=self.name, claimed=work.kind, target=work.target))
        try:
            if work.kind in ("explore", "mission", "variation"):
                await self.explore(work)
            elif work.kind == "replay":
                await self.replay(work)
            elif work.kind in ("confirm", "verify_fix"):
                await self.reproduce(work)
        except Exception as e:  # noqa: BLE001 - one failed item must not kill the worker; its claim will lapse
            log.exception(kv(agent=self.name, failed=work.target, error=str(e)))
        finally:
            self.work = None
        return True

    def renew(self) -> bool:
        """Extend the current claim's lease (Q58, Q58b). False if it was lost: the lease ran out (a slow page
        read, a long route) and another explorer took the work, so this explorer must drop it."""
        w = self.work
        if w is None:
            return True
        now = now_ms()
        if w.job_id:
            return self.graph.one("Q58b", {"id": w.job_id, "agent": self.name, "now": now}) is not None
        if w.kind in ("explore", "mission"):
            return self.graph.one("Q58", {"action": w.target, "agent": self.name, "now": now}) is not None
        return True

    async def bootstrap(self) -> None:
        """Empty map: load the entry page so the first explorer to see it creates and reads it (S1 step 1)."""
        self.heartbeat("working", "entry page")
        ctx, page, _obs = await self.fresh()
        try:
            await self.start(page)
        finally:
            await ctx.close()

    async def fresh(self):
        """A fresh, logged-out browser context restricted to the store's origin."""
        ctx = await self.browser.new_context(accept_downloads=False)
        origin = self.base_url

        async def only_our_origin(r):
            if r.request.url.startswith(origin + "/") or r.request.url == origin:
                await r.continue_()
            else:
                await r.abort()

        await ctx.route("**/*", only_our_origin)
        page = await ctx.new_page()
        page.on("dialog", lambda d: asyncio.ensure_future(d.dismiss()))
        return ctx, page, Observer(page, origin)

    async def start(self, page) -> Arrival | None:
        """Load the entry page; None if the store's release is not the one the graph records."""
        await page.goto(self.base_url + "/", wait_until="load")
        await settle(page, 3000)
        meta = load("scope").get("release_meta", "app-release")
        shown = await page.get_attribute(f'meta[name="{meta}"]', "content")
        if shown and shown != self.release:
            log.info(kv(agent=self.name, waiting_for_release=shown, graph_release=self.release))
            await asyncio.sleep(2)
            return None
        return await self.arrive(page, entry=True)

    async def arrive(self, page, entry: bool = False, prev: Arrival | None = None, via: str | None = None) -> Arrival:
        """Fingerprint the current page, upsert it (Q03), read it if nobody has (Q03b + page reader + Q04),
        and add candidates a release added to an already-read page."""
        page_snap, main_snap = await snapshots(page)
        fp = fingerprint(page.url, page_snap, main_snap)
        cands = extract(page_snap, page.url)
        name = default_name(fp.route, fp.auth, main_snap)
        row = self.graph.one(
            "Q03",
            {
                "key": fp.key,
                "route": fp.route,
                "auth": fp.auth,
                "fingerprint": fp.hash,
                "name": name,
                "url": page.url.replace(self.base_url, ""),
                "agent": self.name,
                "elements": json.dumps([c.to_dict() for c in cands]),
                "entry": entry,
                "now": now_ms(),
            },
        )
        arrival = Arrival(
            fp.key,
            fp.route,
            page.url,
            page_snap,
            main_snap,
            cands,
            path=(prev.path + [via]) if prev and via else [],
            states=(prev.states if prev else []) + [fp.key],
        )
        if row["is_new"]:
            self.graph.publish("state.created", key=fp.key, name=name, by=self.name)
        if not row["read"]:
            claim = self.graph.one(
                "Q03b", {"key": fp.key, "agent": self.name, "now": now_ms(), "lease_ms": lease_ms("read")}
            )
            if claim:
                await self.read(page, arrival, name)
        elif row["previous_elements"]:
            self.add_new_elements(arrival, json.loads(row["previous_elements"]))
        return arrival

    async def read(self, page, arrival: Arrival, name: str) -> None:
        facts = [
            f["text"] for f in self.graph.run("Q26", {"kinds": ["input", "precondition"], "limit": 10}, read_only=True)
        ]
        ctx = page_reader.ReadContext(
            arrival.url,
            await page.title(),
            arrival.candidates,
            arrival.main_snap,
            arrival.page_snap,
            facts,
            default_name=name,
        )
        result, calls = await asyncio.to_thread(page_reader.read_page, ctx)
        self.pending_llm += calls
        rows = page_reader.action_rows(arrival.key, arrival.candidates, result, origin="page_reader")
        self.graph.run(
            "Q04",
            {"state": arrival.key, "name": result.state_name if calls else None, "actions": rows, "now": now_ms()},
        )
        for text in result.facts:
            self.fact(arrival.key, "input", text)
        log.info(kv(agent=self.name, read=arrival.key, actions=len(rows), llm_calls=calls))

    def add_new_elements(self, arrival: Arrival, previous: list[dict]) -> None:
        """A known page shows candidates it didn't have before (e.g. a new nav link in a release): add just
        those, with default cases and no LLM. A removed + added pair with the same role may be a rename, so it
        is left to the heal step instead."""
        before = {f"{p['role']}:{p['target']}": p for p in previous}
        now = {c.identity: c for c in arrival.candidates}
        added = [c for ident, c in now.items() if ident not in before and c.kind != "field"]
        removed_roles = {p["role"] for ident, p in before.items() if ident not in now}
        added = [c for c in added if c.role not in removed_roles]
        if not added:
            return
        keep = {c.id for c in added} | {fid for c in added for fid in c.field_ids}
        subset = [c for c in arrival.candidates if c.id in keep]
        ctx = page_reader.ReadContext(arrival.url, "", subset, arrival.main_snap, arrival.page_snap)
        read = page_reader.validate(page_reader.deterministic_read(ctx), subset, 200)
        rows = page_reader.action_rows(arrival.key, subset, read, origin="page_reader")
        self.graph.run("Q04", {"state": arrival.key, "name": None, "actions": rows, "now": now_ms()})
        log.info(kv(agent=self.name, new_elements=[c.identity for c in added], state=arrival.key))

    def fact(self, about: str, kind: str, text: str) -> None:
        self.graph.run(
            "Q25",
            {
                "about": about,
                "kind": kind,
                "text": text,
                "fact_id": short_id("F"),
                "agent": self.name,
                "release": self.release,
                "now": now_ms(),
            },
        )

    # -- routes ---------------------------------------------------------------------------------------------------
    async def walk(
        self, page, obs: Observer, steps: list[route.Step], here: Arrival, replans: int = 1
    ) -> Arrival | None:
        """Walk known steps. If a step lands on another page than the map expected (drift), re-plan once from
        where we are to the same destination. None if that fails too, or an element is missing."""
        goal = steps[-1].expected if steps else here.key
        for s in steps:
            done = await self.act(page, obs, s.details, here, instance=0)
            if done.arrival is None:
                log.info(kv(agent=self.name, missing=s.key, error=done.performed.error))
                return None
            if done.arrival.key != s.expected:
                log.info(kv(agent=self.name, drift=s.key, expected=s.expected, got=done.arrival.key))
                if replans <= 0 or goal is None:
                    return None
                rest = route.plan(self.graph, done.arrival.key, goal)
                if rest is None:
                    return None
                return await self.walk(page, obs, rest, done.arrival, replans - 1)
            here = done.arrival
            if not self.renew():
                log.info(kv(agent=self.name, lost_claim=self.work.target if self.work else None))
                return None
        return here

    async def go_to(self, page, obs: Observer, state: str) -> Arrival | None:
        """Fresh entry page → shortest known route → `state`. None if unreachable or the route drifted."""
        start = await self.start(page)
        if start is None:
            return None
        steps = route.plan(self.graph, start.key, state)
        if steps is None:
            log.info(kv(agent=self.name, no_route=state))
            return None
        return await self.walk(page, obs, steps, start)

    async def act(self, page, obs: Observer, details: dict, here: Arrival, instance: int, heal: bool = True) -> Outcome:
        """Perform one stored action from `here`, healing a renamed element when possible."""
        sel = json.loads(details.get("selector") or "{}")
        inputs = json.loads(details.get("inputs") or "{}")
        obs.reset()
        started = time.time()
        done = await perform(page, sel, details["kind"], inputs, instance, self.account)
        if not done.ok and done.error == "element missing" and heal:
            healed = await self.heal(page, obs, details, here, instance)
            if healed is not None:
                return healed
        if not done.ok:
            return Outcome(None, done, [], False, int((time.time() - started) * 1000))
        arrival = await self.arrive(page, prev=here, via=details["key"])
        return Outcome(arrival, done, [], True, int((time.time() - started) * 1000))

    async def heal(self, page, obs: Observer, details: dict, here: Arrival, instance: int) -> Outcome | None:
        """The element is gone: try the candidate that plays the same role (§10.8). If it reaches a page this
        action reached before, it's a rename: update the selector (Q21) and remember it as a Fact."""
        state = self.graph.one("Q42", {"key": here.key}, read_only=True) or {"actions": []}
        taken = names_of_other_elements(state["actions"], details)
        outcomes = self.graph.run("Q48", {"action": details["key"]}, read_only=True)
        known = {o["target"] for o in outcomes if o["ok"]}
        target_name = next((o["target_name"] for o in outcomes if o["ok"]), "")
        role = "form" if details["kind"] == "fill_submit" else details["role"]
        old = json.loads(details["selector"])
        old_name = old.get("submit", {}).get("name") if role == "form" else old.get("name", details["name"])
        cand, calls = locate_mod.heal_candidate(role, old_name or "", target_name, here.candidates, taken)
        self.pending_llm += calls
        if cand is None:
            return None
        if role == "form":
            new_sel = dict(old, submit={"role": "button", "name": cand.name})
        else:
            new_sel = {"role": cand.role, "name": cand.name}
        obs.reset()
        started = time.time()
        done = await perform(
            page, new_sel, details["kind"], json.loads(details.get("inputs") or "{}"), instance, self.account
        )
        if not done.ok:
            return None
        arrival = await self.arrive(page, prev=here, via=details["key"])
        ms = int((time.time() - started) * 1000)
        if arrival.key in known:
            text = f"Renamed '{old_name}' → '{cand.name}' in {self.release}"
            self.graph.run(
                "Q21",
                {
                    "action": details["key"],
                    "new_name": normalize(cand.name),
                    "new_label": cand.name if role != "form" else details["label"],
                    "selector": json.dumps(new_sel),
                    "text": text,
                    "fact_id": short_id("F"),
                    "agent": self.name,
                    "release": self.release,
                    "now": now_ms(),
                },
            )
            self.graph.publish("action.healed", action=details["key"], new_name=cand.name)
            log.info(kv(agent=self.name, healed=details["key"], new_name=cand.name))
        return Outcome(arrival, done, [], True, ms)

    # -- explore, mission, variation ---------------------------------------------------------------------------------
    async def explore(self, work: Work) -> None:
        d = route.details(self.graph, [work.target]).get(work.target)
        if d is None:
            return
        instance = work.instance if work.kind == "variation" else 0
        for _attempt in range(2):  # one retry in a fresh context after drift
            ctx, page, obs = await self.fresh()
            try:
                here = await self.go_to(page, obs, work.state)
                if here is None:
                    continue
                await self.perform_and_record(page, obs, work, d, here, instance)
                return
            finally:
                await ctx.close()
        log.info(kv(agent=self.name, gave_up=work.target, note="claim will lapse and be retried"))

    async def perform_and_record(
        self, page, obs: Observer, work: Work, d: dict, here: Arrival, instance: int
    ) -> Outcome | None:
        if not self.renew():
            log.info(kv(agent=self.name, lost_claim=work.target, note="another explorer has it now"))
            return None
        out = await self.act(page, obs, d, here, instance, heal=work.kind in ("replay", "confirm", "verify_fix"))
        events = obs.take()
        if out.arrival is None:
            # the element is missing (and no heal): record that the action now goes nowhere
            out = Outcome(here, out.performed, [], False, out.ms)
            events.append(Event("nav_timeout", out.performed.error or "element missing"))
        values = await testid_values(page)
        problems = problems_from(events, out.arrival.route, out.arrival.key, d["key"], values)
        # The edge is broken (cost 1000, routes go around it) only when navigation itself failed: a server error,
        # an uncaught error or a missing element. A content rule failing on a page that loaded is still a bug,
        # but routes may pass through it, or the page behind it could never be explored.
        hard = [p for p in problems if p.status == "new" and p.kind != "rule"]
        ok = out.performed.ok and not hard
        out.problems, out.ok = problems, ok
        error = (hard[0].message if hard else out.performed.error) if not ok else None
        # Edges describe the default instance (the one routes use). Another instance (variation mode, or a repro
        # of a bug found on, say, the 8th product) only adds an edge to a page not reached before; it never
        # overwrites the default's outcome.
        known = instance != 0 and any(
            o["release"] == self.release and o["target"] == out.arrival.key
            for o in self.graph.run("Q48", {"action": d["key"]}, read_only=True)
        )
        if not known:
            self.graph.run(
                "Q07",
                {
                    "action": d["key"],
                    "target": out.arrival.key,
                    "release": self.release,
                    "ok": ok,
                    "error": error,
                    "ms": out.ms,
                    "agent": self.name,
                    "work_kind": work.kind,
                    "via": json.dumps({"actions": here.path, "states": here.states}),
                    "now": now_ms(),
                },
            )
        step = self.graph.one(
            "Q08",
            {
                "action": d["key"],
                "run": self.run_id,
                "agent": self.name,
                "session": self.session,
                "release": self.release,
                "llm_calls": self.pending_llm,
                "ok": ok,
                "ms": out.ms,
                "work_kind": work.kind,
                "instance": json.dumps(out.performed.instance),
                "now": now_ms(),
            },
        )
        self.pending_llm = 0
        self.graph.publish("transition", action=d["key"], target=out.arrival.key, ok=ok, agent=self.name)
        self.learn(d, out)
        if work.kind not in ("confirm", "verify_fix"):
            for p in problems:
                await self.record_bug(page, p, d, out, step["steps"] if step else 0, work)
        return out

    def learn(self, d: dict, out: Outcome) -> None:
        """Semantic memory: preconditions (redirected to log in) and how inputs were received."""
        if out.arrival is None:
            return
        if out.arrival.route.startswith("/login?") and "log in" not in (d.get("label") or "").lower():
            self.fact(d["key"], "precondition", f"'{d['label']}' requires login")
        if d["kind"] == "fill_submit":
            inputs = json.loads(d.get("inputs") or "{}")
            shown = [v for v in inputs.values() if v and "{{" not in v]
            for msg in messages(out.arrival.main_snap)[:1]:
                if shown:
                    pairs = ", ".join(f"{k} = '{v}'" for k, v in inputs.items() if v and "{{" not in v)
                    self.fact(d["key"], "input", f"{pairs} → '{msg}'")

    async def record_bug(self, page, p: Problem, d: dict, out: Outcome, step_n: int, work: Work) -> None:
        status = "suspect" if work.kind == "replay" else p.status
        shot = await self.screenshot(page, p.sig)
        evidence = {
            "message": p.message,
            "agent": self.name,
            "run": self.run_id,
            "step": step_n,
            "url": out.arrival.url.replace(self.base_url, ""),
            "instance": out.performed.instance,
            "inputs": json.loads(d.get("inputs") or "{}"),
            "release": self.release,
            "screenshot": shot,
            **{k: v for k, v in p.details.items() if k != "values"},
            "values": p.details.get("values"),
        }
        sev = severity(p, self.importance_percentile(d["state"]))
        row = self.graph.one(
            "Q12",
            {
                "action": d["key"],
                "release": self.release,
                "sig": p.sig,
                "kind": p.kind,
                "title": p.title,
                "initial_status": status,
                "severity": sev,
                "evidence": json.dumps(evidence),
                "now": now_ms(),
            },
        )
        if row:
            self.graph.publish("bug.updated", sig=p.sig, status=row["status"], count=row["count"])
            log.info(kv(agent=self.name, bug=p.sig, status=row["status"], count=row["count"]))

    def importance_percentile(self, state_key: str) -> float:
        rows = self.graph.run("Q47", read_only=True)
        scores = sorted(r["importance"] or 0 for r in rows)
        mine = next((r["importance"] or 0 for r in rows if r["key"] == state_key), 0)
        if not scores or scores[-1] == 0:
            return 0.0
        return sum(1 for s in scores if s <= mine) / len(scores)

    async def screenshot(self, page, sig: str) -> str | None:
        try:
            self.screens.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha1(sig.encode()).hexdigest()[:12] + ".png"
            path = self.screens / name
            if not path.exists():
                await page.screenshot(path=str(path), full_page=True)
            return name
        except Exception:  # noqa: BLE001 - evidence is best effort
            return None

    # -- jobs --------------------------------------------------------------------------------------------------------
    def finish(self, work: Work, status: str, result: str) -> None:
        self.graph.run(
            "Q14", {"id": work.job_id, "agent": self.name, "status": status, "result": result, "now": now_ms()}
        )
        self.graph.publish("job.updated", id=work.job_id, status=status, result=result)
        log.info(kv(agent=self.name, job=work.job_id, kind=work.kind, status=status, result=result))

    async def replay(self, work: Work) -> None:
        """Re-run one transition of the previous release on the current one (S4)."""
        d = route.details(self.graph, [work.target]).get(work.target)
        if d is None:
            self.finish(work, "failed", "unknown action")
            return
        via = self.original_route(work.target)
        for attempt in range(2):
            ctx, page, obs = await self.fresh()
            try:
                here = None
                if via and attempt == 0:  # first try the route that produced the previous release's outcome
                    start = await self.start(page)
                    if start and via["states"] and via["states"][0] == start.key:
                        steps = route.steps_for(self.graph, via["actions"], via["states"])
                        here = await self.walk(page, obs, steps, start, replans=0) if steps else start
                if here is None:
                    if via and attempt == 0:
                        await ctx.close()
                        ctx, page, obs = await self.fresh()
                    here = await self.go_to(page, obs, d["state"])
                if here is None:
                    continue
                out = await self.perform_and_record(page, obs, work, d, here, 0)
                if out is None:  # the job's lease ran out and another explorer has it
                    return
                self.finish(work, "done", f"{'ok' if out.ok else 'failed'} → {out.arrival.key}")
                return
            finally:
                await ctx.close()
        self.finish(work, "failed", "could not reach the action's page")

    def original_route(self, action: str) -> dict | None:
        """The route (actions and states from the entry page) behind the previous release's working outcome of
        this action. An outcome can depend on how the page was reached (an empty cart or a full one behind the
        same login page), so a replay walks the same route before comparing releases."""
        prev = self.graph.one("Q49", read_only=True)
        if not prev:
            return None
        for o in self.graph.run("Q48", {"action": action}, read_only=True):
            if o["release"] == prev["previous"] and o["ok"] and o.get("via"):
                via = json.loads(o["via"])
                if via.get("states"):
                    return via
        return None

    async def reproduce(self, work: Work) -> None:
        """confirm: replay the repro steps in a fresh session; verify_fix: the same on a new release."""
        sig = work.target
        bug = self.graph.one("Q38", {"sig": sig}, read_only=True)
        rows = sorted(self.graph.run("Q11", {"sig": sig}, read_only=True), key=lambda r: r["cost"])
        if not bug or not rows or rows[0]["cost"] >= 1000:
            self.finish(work, "failed", "no route to the trigger")
            if work.kind == "confirm" and bug:
                self.graph.run(
                    "Q15", {"sig": sig, "status": "not_reproduced", "severity": None, "title": None, "now": now_ms()}
                )
            return
        evidence = json.loads(bug["evidence"] or "{}")
        best = rows[0]
        steps = route.steps_for(self.graph, best["steps"], best["states"] + [None])
        trigger = steps[-1]
        attempts = int(load("oracles").get("confirm", {}).get("attempts", 2))
        reproduced, reached = False, False
        for _attempt in range(attempts):
            ctx, page, obs = await self.fresh()
            try:
                start = await self.start(page)
                if start is None:
                    continue
                here = await self.walk(page, obs, steps[:-1], start) if len(steps) > 1 else start
                if here is None:
                    continue
                reached = True
                instance = int((evidence.get("instance") or {}).get("index", 0))
                out = await self.perform_and_record(page, obs, work, trigger.details, here, instance)
                if out is None:  # the job's lease ran out and another explorer has it
                    return
                if bug["kind"] == "regression":
                    reproduced = (not out.ok) or out.arrival.key != evidence.get("was_target_key")
                else:
                    reproduced = sig in {p.sig for p in out.problems}
                if reproduced:
                    break
            finally:
                await ctx.close()
        now = now_ms()
        if work.kind == "confirm":
            status = "confirmed" if reproduced else ("not_reproduced" if reached else None)
            if status is None:
                self.finish(work, "failed", "could not reach the trigger")
                return
            self.graph.run("Q15", {"sig": sig, "status": status, "severity": None, "title": None, "now": now})
            self.finish(work, "done", status)
        else:
            if not reached:
                self.finish(work, "failed", "could not reach the trigger")
                return
            if reproduced:
                self.graph.run(
                    "Q12",
                    {
                        "action": trigger.key,
                        "release": self.release,
                        "sig": sig,
                        "kind": bug["kind"],
                        "title": bug["title"],
                        "initial_status": "new",
                        "severity": bug["severity"],
                        "evidence": bug["evidence"],
                        "now": now,
                    },
                )
                self.finish(work, "done", f"still present in {self.release}")
            else:
                self.graph.run("Q22", {"sig": sig, "release": self.release, "now": now})
                self.finish(work, "done", f"fixed in {self.release}")
        self.graph.publish("bug.updated", sig=sig)

    # -- loop --------------------------------------------------------------------------------------------------------
    async def run(self, deadline: float | None = None, idle_exit_s: float | None = None) -> None:
        poll = load("session").get("poll_ms", 1000) / 1000
        idle_since = None
        while deadline is None or time.time() < deadline:
            did = await self.step()
            if did:
                idle_since = None
                continue
            idle_since = idle_since or time.time()
            if idle_exit_s is not None and time.time() - idle_since >= idle_exit_s:
                break
            await asyncio.sleep(poll)
        self.heartbeat("stopped")


def names_of_other_elements(actions: list[dict], details: dict) -> set[str]:
    """Names (and old names) of the page's *other* elements, which a heal must not pick. The other input cases
    of the same form (keys that differ only in the final `:case`) are the same element, so a sibling case that
    was healed first doesn't block this one."""
    key = details["key"]
    element = key.rsplit(":", 1)[0] + ":" if details["kind"] == "fill_submit" else key
    others = [a for a in actions if a.get("key") and a["key"] != key and not a["key"].startswith(element)]
    return {a["name"] for a in others} | {n for a in others for n in (a.get("aliases") or [])}


def account_for(n: int) -> Account:
    """explorer-n uses test account (n - 1) mod 8 + 1 (email pattern `account_email` in config/scope.yaml)."""
    i = (n - 1) % 8 + 1
    pattern = load("scope").get("account_email", "explorer{i}@nebula.test")
    return Account(pattern.format(i=i), env("SHOP_EXPLORER_PASSWORD") or "nebula-pass")


async def main_async(count: int, minutes: float | None, idle_exit_s: float | None, graph: str | None) -> None:
    from playwright.async_api import async_playwright

    db = connect()
    mode = env("CLEW_MODE", "shared")
    shared = Graph(db, graph or graph_name())
    deadline = time.time() + minutes * 60 if minutes else None
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=os.environ.get("HEADED") != "1")
        explorers = []
        for _ in range(count):
            n = shared.incr("explorers")
            name = f"explorer-{n}"
            g = shared
            if mode == "isolated":  # S5 baseline: a private copy of the seed, no shared claims or memory
                g = reset_from(db, seed_graph(), f"iso_{name}")
            explorers.append(Explorer(g, name, browser, account_for(n)))
        await asyncio.gather(*(e.run(deadline, idle_exit_s) for e in explorers))
        await browser.close()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=int(env("EXPLORERS_PER_PROCESS", "1")))
    p.add_argument("--minutes", type=float, default=None)
    p.add_argument("--idle-exit", type=float, default=None, help="stop after this many idle seconds")
    p.add_argument("--graph", default=None)
    a = p.parse_args()
    asyncio.run(main_async(a.count, a.minutes, a.idle_exit, a.graph))


if __name__ == "__main__":
    main()
