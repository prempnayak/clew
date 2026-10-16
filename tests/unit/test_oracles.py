"""Signatures, rule checks and detectors (table-driven, handoff §20)."""

from __future__ import annotations

import pytest

from clew.oracles import signatures
from clew.oracles.checks import cart_count_matches, cart_total, coupon_max_10pct, price_is_number
from clew.oracles.detectors import Event, problems_from


@pytest.mark.parametrize(
    "msg, expected",
    [
        (
            "TypeError: Cannot read properties of null (reading 'url')",
            "typeerror: cannot read properties of null (reading '#')",
        ),
        (
            "TypeError: Cannot read properties of undefined (reading 'productId')",
            "typeerror: cannot read properties of undefined (reading '#')",
        ),
        ("Error at item 12 id deadbeefcafe", "error at item # id #"),
    ],
)
def test_normalize(msg, expected):
    assert signatures.normalize_message(msg) == expected


@pytest.mark.parametrize(
    "fn, values, fails",
    [
        (coupon_max_10pct, {"subtotal": ["120.00"], "discount": ["24.00"]}, True),
        (coupon_max_10pct, {"subtotal": ["120.00"], "discount": ["12.00"]}, False),
        (coupon_max_10pct, {"subtotal": ["19.00"], "discount": ["0.00"]}, False),
        (cart_total, {"subtotal": ["120.00"], "discount": ["24.00"], "total": ["96.00"]}, False),
        (cart_total, {"subtotal": ["120.00"], "discount": ["24.00"], "total": ["100.00"]}, True),
        (price_is_number, {"product-price": ["NaN"]}, True),
        (price_is_number, {"product-price": ["249.00"]}, False),
        (price_is_number, {}, False),
        (cart_count_matches, {"cart-count": ["2"], "line-item": ["a", "b"]}, False),
        (cart_count_matches, {"cart-count": ["3"], "line-item": ["a", "b"]}, True),
    ],
)
def test_rules(fn, values, fails):
    assert (fn(values) is not None) is fails


def test_detectors():
    events = [
        Event("http_5xx", "", url="http://shop:8090/checkout", method="GET", status=500),
        Event("pageerror", "TypeError: Cannot read properties of null (reading 'url')"),
        Event("console_error", "Failed to load resource: the server responded with a status of 404 (Not Found)"),
        Event("console_error", "something odd"),
    ]
    ps = {p.sig: p for p in problems_from(events, "/wishlist", "/wishlist|out|abc", "a")}
    assert ps["http_5xx|GET /checkout|500"].status == "new"
    assert ps["pageerror|/wishlist|typeerror: cannot read properties of null (reading '#')"].status == "new"
    assert ps["console_error|/wishlist|something odd"].status == "suspect"
    assert len(ps) == 3  # the 404 console message is ignored (D3)


def test_rule_problem_signature():
    ps = problems_from(
        [], "/cart", "/cart|out|7e21f0aa", "a", {"subtotal": ["120.00"], "discount": ["24.00"], "total": ["96.00"]}
    )
    assert [p.sig for p in ps] == ["rule|coupon_max_10pct|/cart|7e21f0aa"]


def test_regression_signature_ignores_auth():
    a = signatures.regression("/search?q|out|cdf65eef#button:add to cart")
    b = signatures.regression("/search?q|in|cdf65eef#button:add to cart")
    assert a == b == "regression|/search?q|cdf65eef#button:add to cart"
