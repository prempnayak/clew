"""Performing a stored action in the browser (handoff §10.6).

Locators: links by the route key of their href (link groups pick an instance), everything else by role and
exact accessible name. Forms fill each field by role and name, then click the submit button.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from clew.common.config import load
from clew.explorer.extract import in_scope
from clew.explorer.fingerprint import route_key


@dataclass
class Account:
    email: str
    password: str


@dataclass
class Performed:
    ok: bool  # the element was found and acted on
    error: str | None = None
    instance: dict = field(default_factory=dict)  # index, text, href of the element used


def render(value: str, account: Account) -> str:
    value = value.replace("{{account.email}}", account.email).replace("{{account.password}}", account.password)
    return re.sub(r"\{\{repeat:(.):(\d+)\}\}", lambda m: m.group(1) * int(m.group(2)), value)


async def find_link(page, target_route: str, instance: int):
    links = page.locator("a[href]")
    hrefs = await links.evaluate_all("els => els.map(e => e.getAttribute('href'))")
    matches = []
    for i, href in enumerate(hrefs):
        url = in_scope(href or "", page.url)
        if url and route_key(url) == target_route:
            matches.append(i)
    if not matches:
        return None, 0
    idx = matches[instance % len(matches)]
    return links.nth(idx), len(matches)


async def find_role(page, role: str, name: str, instance: int):
    loc = page.get_by_role(role, name=name, exact=True, disabled=False)
    n = await loc.count()
    if n == 0:
        return None, 0
    return loc.nth(instance % n), n


async def locate(page, selector: dict, kind: str, instance: int):
    """The element to click for this action, or None if it is missing."""
    if kind == "fill_submit":
        submit = selector["submit"]
        return (await find_role(page, submit["role"], submit["name"], 0))[0]
    if "href_route" in selector:
        return (await find_link(page, selector["href_route"], instance))[0]
    return (await find_role(page, selector["role"], selector["name"], instance))[0]


async def settle(page, timeout_ms: int) -> None:
    """Wait for navigation and network to calm down, capped (V6)."""
    await page.wait_for_timeout(150)
    for state in ("load", "networkidle"):
        try:
            await page.wait_for_load_state(state, timeout=timeout_ms)
        except Exception:  # noqa: BLE001 - a busy page is not a failure; the snapshot is taken anyway
            pass


async def perform(page, selector: dict, kind: str, inputs: dict, instance: int, account: Account) -> Performed:
    timeout = int(load("session").get("action_timeout_ms", 5000))
    max_len = int(load("scope").get("max_input_length", 200))
    try:
        if kind == "fill_submit":
            for f in selector["fields"]:
                value = render(inputs.get(f["name"], ""), account)[:max_len]
                loc, _ = await find_role(page, f["role"], f["name"], 0)
                if loc is None:
                    return Performed(False, f"field {f['name']!r} missing")
                await loc.fill(value, timeout=timeout)
        loc = await locate(page, selector, kind, instance)
        if loc is None:
            return Performed(False, "element missing")
        text = (await loc.inner_text(timeout=timeout)).strip()[:80]
        href = await loc.get_attribute("href", timeout=timeout)
        await loc.click(timeout=timeout)
    except Exception as e:  # noqa: BLE001 - Playwright timeouts and detached elements
        return Performed(False, f"{type(e).__name__}: {str(e).splitlines()[0][:200]}")
    await settle(page, int(load("session").get("settle_ms", 5000)))
    return Performed(True, None, {"index": instance, "text": text, "href": href})


async def snapshots(page) -> tuple[str, str]:
    """(whole page, main landmark) ARIA snapshots; `body` when there is no `main`."""
    landmark = load("fingerprint").get("landmark", "main")
    whole = await page.aria_snapshot()
    main = page.locator(landmark)
    if await main.count():
        return whole, await main.first.aria_snapshot()
    return whole, await page.locator("body").aria_snapshot()


async def testid_values(page) -> dict[str, list[str]]:
    rows = await page.locator("[data-testid]").evaluate_all(
        "els => els.map(e => [e.getAttribute('data-testid'), (e.textContent || '').trim()])")
    out: dict[str, list[str]] = {}
    for k, v in rows:
        out.setdefault(k, []).append(v)
    return out


def selector_of(details: dict) -> dict:
    return json.loads(details.get("selector") or "{}")
