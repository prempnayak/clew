"""State fingerprint: `route|auth|hash8`. The riskiest part of Clew, so it is config-driven
(config/fingerprint.yaml) and tested on snapshot fixtures of every store page (tests/unit/test_fingerprint.py).

- route: URL path with id-like segments as `:id` (plus configured patterns), query keys sorted, values dropped.
- auth: `in` if any element on the page matches the log-out pattern, else `out`.
- hash8: SHA-1 of structural tokens from the ARIA snapshot of `main`: headings by level, interactive elements
  by role only (names excluded, so a renamed button keeps its state), collections as empty/some with only the
  first item tokenized, transient feedback and text skipped.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import parse_qsl, urlsplit

from clew.common.config import load

LINE = re.compile(r'^(?P<indent>\s*)- (?P<role>[a-z]+)(?: "(?P<name>(?:[^"\\]|\\.)*)")?(?P<rest>.*)$')
URL_LINE = re.compile(r"^(?P<indent>\s*)- /url: (?P<url>.*)$")
ID_SEG = re.compile(r"^(\d+|[0-9a-f]{8,}|[0-9a-f-]{36})$", re.I)


@dataclass(frozen=True)
class FingerprintConfig:
    route_params: tuple[str, ...]
    auth_in_pattern: str
    landmark: str
    interactive_roles: frozenset[str]
    collection_roles: frozenset[str]
    item_roles: frozenset[str]
    transient_roles: frozenset[str]
    ignored_roles: frozenset[str]
    hash_chars: int


@lru_cache(maxsize=1)
def config() -> FingerprintConfig:
    c = load("fingerprint")
    return FingerprintConfig(
        route_params=tuple(c.get("route_params", [])),
        auth_in_pattern=c["auth_in_pattern"],
        landmark=c.get("landmark", "main"),
        interactive_roles=frozenset(c["interactive_roles"]),
        collection_roles=frozenset(c["collection_roles"]),
        item_roles=frozenset(c.get("item_roles", ["listitem", "row", "article"])),
        transient_roles=frozenset(c["transient_roles"]),
        ignored_roles=frozenset(c["ignored_roles"]),
        hash_chars=int(c.get("hash_chars", 8)),
    )


@dataclass
class Node:
    """One line of an ARIA snapshot."""

    depth: int
    role: str
    name: str
    rest: str
    url: str | None = None

    @property
    def disabled(self) -> bool:
        return "[disabled" in self.rest

    @property
    def text(self) -> str:
        """Inline text after the colon, e.g. `- status: Coupon applied.`"""
        r = re.sub(r"\[[^\]]*\]", "", self.rest).strip()
        return r[1:].strip().strip('"') if r.startswith(":") else ""


def parse(snapshot: str) -> list[Node]:
    """Every node line of an ARIA snapshot; `/url:` children are attached to their link."""
    nodes: list[Node] = []
    for line in snapshot.splitlines():
        m = LINE.match(line)
        if m:
            name = (m["name"] or "").replace('\\"', '"')
            nodes.append(Node(len(m["indent"]) // 2, m["role"], name, m["rest"]))
            continue
        u = URL_LINE.match(line)
        if u and nodes:
            depth = len(u["indent"]) // 2
            for n in reversed(nodes):
                if n.depth == depth - 1:
                    n.url = u["url"].strip().strip('"')
                    break
    return nodes


def route_key(url: str, route_params: tuple[str, ...] | None = None) -> str:
    """`/product/12` → `/product/:id`, `/search?q=lens` → `/search?q`, `/login?next=/x` → `/login?next`."""
    if route_params is None:
        route_params = config().route_params
    parts = urlsplit(url)
    segs = [":id" if ID_SEG.match(s) else s for s in parts.path.split("/")]
    path = "/".join(segs) or "/"
    for pattern in route_params:
        prefix = pattern.rsplit("/", 1)[0]
        if path.startswith(prefix + "/") and path.count("/") == pattern.count("/"):
            path = pattern
    keys = sorted({k for k, _ in parse_qsl(parts.query, keep_blank_values=True)})
    return path + ("?" + "&".join(keys) if keys else "")


def structure_tokens(main_snapshot: str, cfg: FingerprintConfig | None = None) -> list[str]:
    cfg = cfg or config()
    tokens: list[str] = []
    skip_below: int | None = None
    seen_item_at: dict[int, bool] = {}
    for n in parse(main_snapshot):
        if skip_below is not None and n.depth > skip_below:
            continue  # inside a skipped subtree
        skip_below = None
        role, rest = n.role, n.rest
        if role in cfg.transient_roles:
            skip_below = n.depth
            continue
        if role in cfg.collection_roles:
            has_items = rest.strip().endswith(":")
            tokens.append(f"{role}:{'some' if has_items else 'empty'}")
            seen_item_at[n.depth + 1] = False
            continue
        if role in cfg.item_roles:  # tokenize the first item only
            if seen_item_at.get(n.depth):
                skip_below = n.depth
                continue
            seen_item_at[n.depth] = True
            tokens.append(role)
            continue
        if role == "heading":
            level = re.search(r"\[level=(\d)\]", rest)
            tokens.append(f"heading:{level.group(1) if level else '?'}")
        elif role in cfg.interactive_roles:
            tokens.append(role)  # names deliberately excluded
        elif role not in cfg.ignored_roles:
            tokens.append(role)
    return tokens


def structure_hash(main_snapshot: str, cfg: FingerprintConfig | None = None) -> str:
    cfg = cfg or config()
    joined = "|".join(structure_tokens(main_snapshot, cfg))
    return hashlib.sha1(joined.encode()).hexdigest()[: cfg.hash_chars]


def auth_of(page_snapshot: str, cfg: FingerprintConfig | None = None) -> str:
    cfg = cfg or config()
    pattern = re.compile(cfg.auth_in_pattern)
    for n in parse(page_snapshot):
        if n.role in ("link", "button", "menuitem") and pattern.search(n.name):
            return "in"
    return "out"


@dataclass(frozen=True)
class Fingerprint:
    key: str
    route: str
    auth: str
    hash: str


def fingerprint(url: str, page_snapshot: str, main_snapshot: str) -> Fingerprint:
    cfg = config()
    route = route_key(url, cfg.route_params)
    auth = auth_of(page_snapshot, cfg)
    h = structure_hash(main_snapshot, cfg)
    return Fingerprint(f"{route}|{auth}|{h}", route, auth, h)


def default_name(route: str, auth: str, main_snapshot: str) -> str:
    """Name for people when no LLM names the page: the H1 (or the route for parameter pages) plus qualifiers."""
    nodes = parse(main_snapshot)
    h1 = next((n.name for n in nodes if n.role == "heading" and "[level=1]" in n.rest), "")
    path = route.split("?")[0]
    if ":" in path or not h1:
        words = [s for s in path.split("/") if s and not s.startswith(":")]
        base = " ".join(words).replace("-", " ").capitalize() or "Home"
    else:
        base = h1
    quals = []
    tokens = structure_tokens(main_snapshot)
    if any(t.endswith(":empty") for t in tokens) or (
        not any(t.endswith(":some") for t in tokens)
        and any("empty" in (n.text or n.name).lower() for n in nodes if n.role in ("paragraph", "text", "status"))
    ):
        quals.append("empty")
    names = [n.name for n in nodes if n.role in ("button", "link")]
    for hint in load("fingerprint").get("name_hints", []):
        if hint.get("route") and not re.search(hint["route"], route):
            continue
        if hint.get("token") and hint["token"] not in tokens:
            continue
        if hint.get("candidate") and not any(re.search(hint["candidate"], x) for x in names):
            continue
        quals.append(hint["add"])
    if "?" in route:
        quals.append(route.split("?", 1)[1])
    if auth == "in":
        quals.append("logged in")
    return base + (f" ({', '.join(quals)})" if quals else "")
