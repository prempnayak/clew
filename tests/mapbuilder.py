"""Builds a small Nebula Gear-shaped map through the real queries (Q03, Q04, Q07), for query tests."""

from __future__ import annotations

import json

from clew.graph.client import Graph


def state(g: Graph, key: str, name: str, entry: bool = False, now: int = 10) -> None:
    route, auth, _ = key.split("|")
    g.run(
        "Q03",
        {
            "key": key,
            "route": route,
            "auth": auth,
            "fingerprint": key,
            "name": name,
            "url": route,
            "agent": "test",
            "elements": "[]",
            "entry": entry,
            "now": now,
        },
    )


def action(
    g: Graph,
    state_key: str,
    target: str,
    label: str,
    *,
    kind: str = "click",
    case: str | None = None,
    policy: str = "first",
    priority: int = 5,
    status: str = "untried",
    now: int = 10,
) -> str:
    key = f"{state_key}#{'form' if kind == 'fill_submit' else 'button'}:{target}" + (f":{case}" if case else "")
    g.run(
        "Q04",
        {
            "state": state_key,
            "name": None,
            "now": now,
            "actions": [
                {
                    "key": key,
                    "label": label,
                    "role": "button",
                    "name": target,
                    "by": "role",
                    "selector": json.dumps({"role": "button", "name": label}),
                    "kind": kind,
                    "input_case": case,
                    "inputs": "{}",
                    "instance_policy": policy,
                    "status": status,
                    "skip_reason": None,
                    "priority": priority,
                    "origin": "test",
                }
            ],
        },
    )
    return key


def lead(
    g: Graph,
    action_key: str,
    target: str,
    release: str = "v1",
    ok: bool = True,
    work_kind: str = "explore",
    now: int = 20,
) -> None:
    g.run(
        "Q07",
        {
            "action": action_key,
            "target": target,
            "release": release,
            "ok": ok,
            "error": None if ok else "boom",
            "ms": 5,
            "agent": "test",
            "work_kind": work_kind,
            "via": "{}",
            "now": now,
        },
    )


HOME = "/|out|aaaaaaaa"
PRODUCT = "/product/:id|out|bbbbbbbb"
CART_EMPTY = "/cart|out|cccccccc"
CART_ITEMS = "/cart|out|dddddddd"
CART_COUPON = "/cart|out|eeeeeeee"
SEARCH = "/search?q|out|ffffffff"
LOGIN_NEXT = "/login?next|out|11111111"
CHECKOUT_500 = "/checkout|in|22222222"


def nebula_map(g: Graph) -> dict[str, str]:
    """Home → Product → Cart(items) → coupon; Home → Cart(empty) → Login → 500; Home → Search → Cart(items)."""
    state(g, HOME, "Home (logged out)", entry=True)
    for k, n in [
        (PRODUCT, "Product"),
        (CART_EMPTY, "Cart (empty)"),
        (CART_ITEMS, "Cart (with items)"),
        (CART_COUPON, "Cart (coupon applied)"),
        (SEARCH, "Search results"),
        (LOGIN_NEXT, "Log in"),
        (CHECKOUT_500, "Checkout error"),
    ]:
        state(g, k, n)
    a = {
        "open_product": action(g, HOME, "/product/:id", "Open product", policy="round_robin"),
        "cart_icon": action(g, HOME, "/cart", "Cart"),
        "search": action(g, HOME, "search", "Search", kind="fill_submit", case="valid"),
        "add_to_cart": action(g, PRODUCT, "add to cart", "Add to cart"),
        "apply_coupon": action(g, CART_ITEMS, "apply", "Apply", kind="fill_submit", case="valid", priority=8),
        "apply_again": action(g, CART_COUPON, "apply", "Apply", kind="fill_submit", case="valid", priority=8),
        "checkout_empty": action(g, CART_EMPTY, "proceed to checkout", "Proceed to checkout"),
        "login_valid": action(g, LOGIN_NEXT, "log in", "Log in", kind="fill_submit", case="valid"),
        "search_add": action(g, SEARCH, "add to cart", "Add to cart", policy="round_robin"),
    }
    lead(g, a["open_product"], PRODUCT)
    lead(g, a["cart_icon"], CART_EMPTY)
    lead(g, a["search"], SEARCH)
    lead(g, a["add_to_cart"], CART_ITEMS)
    lead(g, a["apply_coupon"], CART_COUPON)
    lead(g, a["apply_again"], CART_COUPON)
    lead(g, a["checkout_empty"], LOGIN_NEXT)
    lead(g, a["login_valid"], CHECKOUT_500, ok=False)
    lead(g, a["search_add"], CART_ITEMS)
    return a
