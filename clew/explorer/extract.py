"""Candidate actions, extracted deterministically from the whole page's ARIA snapshot (handoff §10.4).

- Links are grouped by the route key of their URL: 12 product cards become one "Open product" candidate.
- Buttons are grouped by role and normalized name: every search result's "Add to cart" is one candidate.
- Fields directly before a button form one fill_submit candidate (the page reader can confirm or correct it).
- Scope filter: same origin only, no mailto/tel, never the `/__*` test hooks, at most N candidates.

The page reader may only pick from these ids; anything else it returns is dropped.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from urllib.parse import urljoin, urlsplit

from clew.common.config import load
from clew.explorer.fingerprint import Node, parse, route_key

FIELD_ROLES = {"textbox", "searchbox", "combobox", "spinbutton"}
CLICK_ROLES = {"link", "button", "tab", "menuitem", "checkbox", "radio", "switch"}


def normalize(name: str) -> str:
    """Lower-case, digits → '#', whitespace collapsed: "Cart (2)" → "cart (#)"."""
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", name.lower())).strip()


@dataclass
class Candidate:
    id: str
    role: str
    name: str
    kind: str  # click | fill_submit | field
    target: str  # identity: route pattern for links, normalized name otherwise
    region: str  # main | nav | other
    count: int = 1
    href: str | None = None
    field_ids: list[str] = field(default_factory=list)

    @property
    def identity(self) -> str:
        return f"{self.role}:{self.target}"

    def to_dict(self) -> dict:
        return asdict(self)


def _region_of(stack: list[Node]) -> str:
    roles = {n.role for n in stack}
    if "main" in roles:
        return "main"
    if "navigation" in roles or "banner" in roles:
        return "nav"
    return "other"


def in_scope(href: str, page_url: str, scope: dict | None = None) -> str | None:
    """The absolute same-origin URL for a link, or None if it is out of scope."""
    scope = scope or load("scope")
    if not href or re.match(r"^(mailto|tel|javascript):", href, re.I):
        return None
    absolute = urljoin(page_url, href)
    a, p = urlsplit(absolute), urlsplit(page_url)
    if (a.scheme, a.netloc) != (p.scheme, p.netloc):
        return None
    path = a.path + (f"?{a.query}" if a.query else "")
    for pattern in scope.get("deny_paths", []):
        if re.search(pattern, path):
            return None
    return absolute


def extract(page_snapshot: str, page_url: str, scope: dict | None = None) -> list[Candidate]:
    scope = scope or load("scope")
    limit = int(scope.get("max_candidates_per_page", 30))
    nodes = parse(page_snapshot)
    out: list[Candidate] = []
    by_identity: dict[str, Candidate] = {}
    pending_fields: list[Candidate] = []
    stack: list[Node] = []
    counter = 0

    def next_id() -> str:
        nonlocal counter
        counter += 1
        return f"c{counter}"

    for n in nodes:
        while stack and stack[-1].depth >= n.depth:
            stack.pop()
        region = _region_of(stack)
        stack.append(n)
        if n.disabled:
            continue
        if n.role in FIELD_ROLES and n.name:
            f = Candidate(next_id(), n.role, n.name, "field", normalize(n.name), region)
            out.append(f)
            pending_fields.append(f)
            continue
        if n.role not in CLICK_ROLES:
            continue
        if n.role == "link":
            pending_fields = []
            url = in_scope(n.url or "", page_url, scope)
            if not url:
                continue
            target = route_key(url)
            ident = f"link:{target}"
            if ident in by_identity:
                by_identity[ident].count += 1
                continue
            path = urlsplit(url)
            c = Candidate(
                next_id(),
                "link",
                n.name,
                "click",
                target,
                region,
                href=path.path + (f"?{path.query}" if path.query else ""),
            )
        else:
            if not n.name:
                continue
            target = normalize(n.name)
            if n.role == "button" and pending_fields:
                fields_key = "+".join(f.target for f in pending_fields)
                ident = f"form:{fields_key}"
                if ident in by_identity:
                    pending_fields = []
                    continue
                c = Candidate(
                    next_id(),
                    "form",
                    n.name,
                    "fill_submit",
                    fields_key,
                    region,
                    field_ids=[f.id for f in pending_fields],
                )
                pending_fields = []
            else:
                pending_fields = []
                ident = f"{n.role}:{target}"
                if ident in by_identity:
                    by_identity[ident].count += 1
                    continue
                c = Candidate(next_id(), n.role, n.name, "click", target, region)
        by_identity[c.identity] = c
        out.append(c)
    # keep forms' fields; cap the number of actionable candidates
    actionable = [c for c in out if c.kind != "field"][:limit]
    keep_fields = {fid for c in actionable for fid in c.field_ids}
    return [c for c in out if c in actionable or c.id in keep_fields]


def page_text(page_snapshot: str) -> str:
    """All names and inline text of a snapshot, for code-like values printed on the page."""
    parts = []
    for n in parse(page_snapshot):
        parts.append(n.name)
        parts.append(n.text)
    return " ".join(p for p in parts if p)


def messages(main_snapshot: str) -> list[str]:
    """Status and alert messages shown on a page (e.g. after a form submit)."""
    return [n.text or n.name for n in parse(main_snapshot) if n.role in ("status", "alert") and (n.text or n.name)]
