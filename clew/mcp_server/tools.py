"""The tools behind Clew's MCP server. Each one is a named query (or two) plus validation.

`Tools` methods take `agent=` (who is calling, from the bearer token) and return plain dicts:
`{"ok": true, ...}` or `{"ok": false, "error": ...}`; they never raise to the model. The MCP server wraps them
with docstrings for the model; the deterministic Reporter calls them directly, so both paths write the same
ToolCall audit trail.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field

from clew.common.config import load
from clew.common.ids import now_ms
from clew.explorer import page_reader
from clew.explorer.extract import Candidate
from clew.graph.client import Graph
from clew.mcp_server.audit import audited
from clew.reporter.github import GitHub

SEVERITIES = {"P1", "P2", "P3"}
SET_STATUSES = {"confirmed", "not_reproduced", "new"}


# -- input and output models --------------------------------------------------------------------------------------
class CaseIn(BaseModel):
    """One input case for add_cases: values keyed by field element id (from state_detail's elements)."""

    case: str = Field(max_length=20)
    values: dict[str, str]


class Step(BaseModel):
    n: int
    text: str
    action: str


class ReproOut(BaseModel):
    ok: bool = True
    steps: list[Step]
    text: str
    summary: str = ""


def placeholder(value: str) -> str:
    return value.replace("{{account.email}}", "<test account email>").replace(
        "{{account.password}}", "<test account password>"
    )


def describe(d: dict, instance: dict | None = None) -> str:
    """A readable step: Click link "Mystery Meteorite" (`/product/1`); Fill "Coupon code" = SAVE10, click "Apply"."""
    sel = json.loads(d.get("selector") or "{}")
    if d["kind"] == "fill_submit":
        inputs = json.loads(d.get("inputs") or "{}")
        fills = ", ".join(f'"{k}" = {placeholder(v) or "(empty)"}' for k, v in inputs.items())
        return f'Fill {fills}, click "{sel.get("submit", {}).get("name", d["label"])}"'
    if "href_route" in sel:
        text = (instance or {}).get("text") or sel.get("name") or d["label"]
        href = (instance or {}).get("href") or sel.get("href") or sel["href_route"]
        return f'Click link "{text}" (`{href}`)'
    return f'Click {sel.get("role", "button")} "{sel.get("name", d["label"])}"'


class Tools:
    def __init__(self, graph: Graph, github: GitHub | None = None):
        self.graph = graph
        self.github = github or GitHub()

    def _bug(self, sig: str) -> dict | None:
        return self.graph.one("Q38", {"sig": sig}, read_only=True)

    # -- Reporter: reading ----------------------------------------------------------------------------------------
    @audited
    def get_bug(self, sig: str, *, agent: str) -> dict:
        b = self._bug(sig)
        if not b:
            return {"ok": False, "error": f"unknown bug {sig}"}
        ev = json.loads(b["evidence"] or "{}")
        return {
            "ok": True,
            "sig": sig,
            "kind": b["kind"],
            "title": b["title"],
            "status": b["status"],
            "severity": b["severity"],
            "pages": b["pages"],
            "count": b["count"],
            "release_found": b["release_found"],
            "seen_in": b["seen_in"],
            "issue": b["issue"],
            "evidence": ev,
            "found_by": {"agent": ev.get("agent"), "run": ev.get("run"), "step": ev.get("step")},
            "summary": b["title"],
        }

    def repro(self, sig: str) -> ReproOut | None:
        rows = sorted(self.graph.run("Q11", {"sig": sig}, read_only=True), key=lambda r: r["cost"])
        if not rows or rows[0]["cost"] >= 1000:
            return None
        keys = rows[0]["steps"]
        details = {r["key"]: r for r in self.graph.run("Q10b", {"keys": keys}, read_only=True)}
        ev = json.loads((self._bug(sig) or {}).get("evidence") or "{}")
        steps = [Step(n=1, text="Open `/` in a fresh, logged-out browser", action="")]
        for i, k in enumerate(keys):
            inst = ev.get("instance") if i == len(keys) - 1 else None
            steps.append(Step(n=i + 2, text=describe(details[k], inst), action=k))
        text = "\n".join(f"{s.n}. {s.text}" for s in steps)
        return ReproOut(steps=steps, text=text, summary=f"{len(steps)} steps")

    @audited
    def repro_steps(self, sig: str, *, agent: str) -> dict:
        r = self.repro(sig)
        if r is None:
            return {"ok": False, "error": f"no known route to bug {sig}"}
        return r.model_dump()

    @audited
    def similar_bugs(self, sig: str, *, agent: str) -> dict:
        if not self._bug(sig):
            return {"ok": False, "error": f"unknown bug {sig}"}
        rows = self.graph.run("Q36", {"sig": sig}, read_only=True)
        return {"ok": True, "similar": rows, "summary": f"{len(rows)} similar"}

    @audited
    def affected_pages(self, action: str, *, agent: str) -> dict:
        rows = self.graph.run("Q35", {"action": action}, read_only=True)
        return {"ok": True, "pages": sorted({r["page"] for r in rows})}

    @audited
    def release_diff(self, previous: str, current: str, *, agent: str) -> dict:
        rows = self.graph.run("Q19", {"previous": previous, "release": current}, read_only=True)
        return {"ok": True, "changed": rows, "summary": f"{len(rows)} changed transitions"}

    # -- Reporter: writing ------------------------------------------------------------------------------------------
    @audited
    def set_bug(
        self, sig: str, status: str | None = None, severity: str | None = None, title: str | None = None, *, agent: str
    ) -> dict:
        if not self._bug(sig):
            return {"ok": False, "error": f"unknown bug {sig}"}
        if status is not None and status not in SET_STATUSES:
            return {"ok": False, "error": f"status must be one of {sorted(SET_STATUSES)}"}
        if severity is not None and severity not in SEVERITIES:
            return {"ok": False, "error": "severity must be P1, P2 or P3"}
        row = self.graph.one(
            "Q15",
            {
                "sig": sig,
                "status": status,
                "severity": severity,
                "title": title[:120] if title else None,
                "now": now_ms(),
            },
        )
        return {"ok": True, "status": row["status"]}

    @audited
    def mark_same_as(self, sig: str, other: str, reason: str, *, agent: str) -> dict:
        if not self._bug(sig) or not self._bug(other):
            return {"ok": False, "error": "unknown bug signature"}
        row = self.graph.one("Q36b", {"sig": sig, "other": other, "reason": reason[:300], "now": now_ms()})
        if not row:
            return {"ok": False, "error": "a bug cannot be the same as itself"}
        return {"ok": True, "same_as": other, "summary": f"merged into {other}"}

    @audited
    def file_issue(self, sig: str, title: str, body: str, labels: list[str], *, agent: str) -> dict:
        b = self._bug(sig)
        if not b:
            return {"ok": False, "error": f"unknown bug {sig}"}
        if b["status"] != "confirmed":
            return {"ok": False, "error": f"only confirmed bugs are filed (status is {b['status']})"}
        allowed = {lbl["name"] for lbl in load("github")["labels"]}
        bad = [lbl for lbl in labels if lbl not in allowed]
        if bad:
            return {"ok": False, "error": f"unknown labels {bad}"}
        if not title.strip() or len(title) > 120:
            return {"ok": False, "error": "title must be 1-120 characters"}
        body = body[:20000] + f"\n\n_Filed by Clew. Graph bug `{sig}`._"
        dry_n = self.graph.one("Q41", {"name": "issue"})["v"]
        issue = self.github.create(title, body, labels, dry_n)
        self.graph.run(
            "Q15b",
            {"sig": sig, "number": issue.number, "url": issue.url, "title": title, "body": body, "now": now_ms()},
        )
        self.graph.publish("bug.updated", sig=sig, status="filed", issue=issue.number)
        return {
            "ok": True,
            "issue": issue.number,
            "url": issue.url,
            "mode": self.github.mode,
            "summary": f"issue #{issue.number}",
        }

    @audited
    def comment_issue(self, sig: str, body: str, *, agent: str) -> dict:
        b = self._bug(sig)
        if not b or not b["issue"]:
            return {"ok": False, "error": "bug has no issue"}
        self.github.comment(b["issue"], body[:10000])
        return {"ok": True, "issue": b["issue"], "summary": f"commented on #{b['issue']}"}

    @audited
    def close_issue(self, sig: str, reason: str, *, agent: str) -> dict:
        b = self._bug(sig)
        if not b or not b["issue"]:
            return {"ok": False, "error": "bug has no issue"}
        if b["status"] != "fixed":
            return {"ok": False, "error": "only fixed bugs are closed"}
        self.github.comment(b["issue"], reason[:2000])
        self.github.close(b["issue"])
        return {"ok": True, "issue": b["issue"], "summary": f"closed #{b['issue']}"}

    # -- Strategist -----------------------------------------------------------------------------------------------
    @audited
    def coverage_gaps(self, limit: int = 10, *, agent: str) -> dict:
        return {"ok": True, "pages": self.graph.run("Q24", {"limit": max(1, min(limit, 50))}, read_only=True)}

    @audited
    def state_detail(self, key: str, *, agent: str) -> dict:
        s = self.graph.one("Q42", {"key": key}, read_only=True)
        if not s:
            return {"ok": False, "error": f"unknown state {key}"}
        s["elements"] = json.loads(s["elements"] or "[]")
        s["actions"] = [a for a in s["actions"] if a.get("key")]
        return {"ok": True, **s}

    @audited
    def facts(self, kinds: list[str], limit: int = 20, *, agent: str) -> dict:
        kinds = [k for k in kinds if k in ("precondition", "input", "rename", "note")] or ["input"]
        return {
            "ok": True,
            "facts": self.graph.run("Q26", {"kinds": kinds, "limit": max(1, min(limit, 50))}, read_only=True),
        }

    def cases_rows(
        self, state: str, element_ids: list[str], cases: list[CaseIn], origin: str, priority: int
    ) -> list[dict] | str:
        """Q04 rows for new input cases on a known form, validated against the state's stored elements."""
        s = self.graph.one("Q42", {"key": state}, read_only=True)
        if not s:
            return f"unknown state {state}"
        elements = [Candidate(**e) for e in json.loads(s["elements"] or "[]")]
        by_id = {e.id: e for e in elements}
        forms = [by_id[i] for i in element_ids if i in by_id and by_id[i].kind == "fill_submit"]
        if not forms:
            return "element_ids must include a form (fill_submit element) from state_detail"
        form = forms[0]
        cases = [c if isinstance(c, CaseIn) else CaseIn.model_validate(c) for c in cases]
        max_len = int(load("scope").get("max_input_length", 200))
        good = []
        for c in cases[:5]:
            if any(fid not in form.field_ids or len(v) > max_len for fid, v in c.values.items()):
                continue
            if any("{{" in v for v in c.values.values()):
                continue
            name = re.sub(r"[^a-z0-9_]+", "_", c.case.lower()).strip("_")[:20] or "case"
            good.append(
                page_reader.InputCase(
                    case=f"{origin}-{name}",
                    values=[page_reader.FieldValue(field_id=f, value=c.values.get(f, "")) for f in form.field_ids],
                )
            )
        if not good:
            return "no valid cases (values must be keyed by the form's field ids, at most 200 characters)"
        read = page_reader.PageRead(
            state_name=s["name"],
            actions=[
                page_reader.ProposedAction(
                    candidate_id=form.id, kind="fill_submit", field_ids=form.field_ids, input_cases=good, priority=10
                )
            ],
        )
        subset = [form] + [by_id[f] for f in form.field_ids]
        return page_reader.action_rows(state, subset, read, origin=origin, priority_boost=priority - 10)

    @audited
    def add_cases(self, state: str, element_ids: list[str], cases: list[CaseIn], *, agent: str) -> dict:
        rows = self.cases_rows(state, element_ids, cases, "strategist", 12)
        if isinstance(rows, str):
            return {"ok": False, "error": rows}
        self.graph.run("Q04", {"state": state, "name": None, "actions": rows, "now": now_ms()})
        return {"ok": True, "actions": [r["key"] for r in rows], "summary": f"{len(rows)} cases"}

    @audited
    def add_mission(self, state: str, text: str, *, agent: str) -> dict:
        m = self.graph.one("Q27", {"state": state, "text": text[:300], "by": agent, "now": now_ms()})
        if not m:
            return {"ok": False, "error": f"unknown state {state}"}
        return {"ok": True, "mission": m["mission"]}

    @audited
    def map_summary(self, *, agent: str) -> dict:
        return {"ok": True, **self.graph.one("Q23", read_only=True)}
