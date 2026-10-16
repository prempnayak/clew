"""Rule checks (handoff §12.1). Each takes the page's data-testid values and returns a failure message or None.

Values come from `data-testid` attributes, as a dict testid -> list of texts. config/checks.yaml maps each rule
to the route patterns it runs on.
"""

from __future__ import annotations

import math
from collections.abc import Callable

Values = dict[str, list[str]]


def _num(values: Values, testid: str) -> float | None:
    texts = values.get(testid)
    if not texts:
        return None
    try:
        v = float(texts[0].replace(",", "").strip())
    except ValueError:
        return math.nan
    return v


def cart_total(values: Values) -> str | None:
    """total = subtotal - discount (±0.01)."""
    s, d, t = _num(values, "subtotal"), _num(values, "discount"), _num(values, "total")
    if None in (s, d, t):
        return None
    if math.isnan(s) or math.isnan(d) or math.isnan(t) or abs(t - (s - d)) > 0.01:
        return f"total {t} != subtotal {s} - discount {d}"
    return None


def coupon_max_10pct(values: Values) -> str | None:
    """With a coupon applied, the discount is at most 10% of the subtotal."""
    s, d = _num(values, "subtotal"), _num(values, "discount")
    if s is None or d is None or d <= 0:
        return None
    if d > 0.10 * s + 0.01:
        return f"discount {d:.2f} is more than 10% of subtotal {s:.2f}"
    return None


def price_is_number(values: Values) -> str | None:
    """The product price parses as a number."""
    texts = values.get("product-price")
    if not texts:
        return None
    p = _num(values, "product-price")
    if p is None or math.isnan(p):
        return f"price renders as {texts[0]!r}"
    return None


def cart_count_matches(values: Values) -> str | None:
    """The navigation's cart count equals the number of cart lines."""
    count = _num(values, "cart-count")
    if count is None or math.isnan(count):
        return None
    lines = len(values.get("line-item", []))
    if int(count) != lines:
        return f"cart count {int(count)} but {lines} line(s)"
    return None


RULES: dict[str, Callable[[Values], str | None]] = {
    "cart_total": cart_total,
    "coupon_max_10pct": coupon_max_10pct,
    "price_is_number": price_is_number,
    "cart_count_matches": cart_count_matches,
}


def run_checks(route: str, values: Values, mapping: dict[str, list[str]]) -> list[tuple[str, str]]:
    """(rule id, message) for every rule mapped to this route that fails."""
    out = []
    for rule_id, routes in mapping.items():
        if route in routes and rule_id in RULES:
            msg = RULES[rule_id](values)
            if msg:
                out.append((rule_id, msg))
    return out
