"""The fingerprint equivalence table on real snapshots of every store page (V2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from clew.explorer.fingerprint import default_name, fingerprint, route_key

SNAPS = Path(__file__).parent.parent / "fixtures" / "snapshots"


def key(name: str) -> str:
    d = json.loads((SNAPS / f"{name}.json").read_text())
    return fingerprint("http://shop:8090" + d["url"], d["page"], d["main"]).key


@pytest.mark.parametrize(
    "a, b, same",
    [
        ("product_2_v1", "product_7_v1", True),  # same route key and structure
        ("product_1_v1", "product_2_v1", True),  # the placeholder image is still an image
        ("product_8_v1", "product_2_v1", True),  # a NaN price is content, not structure
        ("product_9_v1", "product_2_v1", False),  # out of stock: an extra "Notify me" button
        ("cart_empty_out_v1", "cart_items_out_v1", False),  # list:empty vs list:some; coupon form only with items
        ("cart_items_out_v1", "cart_coupon_v1", False),  # extra "Remove coupon" makes B1 reachable
        ("cart_coupon_v1", "cart_coupon_flash_v1", True),  # the status message is transient
        ("cart_coupon_v1", "cart_coupon_two_items_v1", True),  # 1 or 2 cart lines: same state
        ("search_telescope_v1", "search_star_v1", True),  # query values dropped (3 results vs 1)
        ("search_star_v1", "search_none_v1", False),  # no results is a different page
        ("search_blank_v1", "search_star_v1", False),  # /search vs /search?q
        ("home_out_v1", "home_in_v1", False),  # auth part of the key
        ("login_v1", "login_next_v1", False),  # different query keys
        ("product_2_v1", "product_2_v2", True),  # "Add to bag": names are not in the hash
        ("home_out_v1", "home_out_v2", True),  # v2's "Gift cards" link is outside main
        ("cart_items_out_v1", "cart_items_out_v2", True),
        ("search_star_v1", "search_star_v2", True),  # data-idx vs data-index is not structure
        ("cart_empty_out_v2", "cart_notice_v2", False),  # new query key
        ("category_maps_v1", "category_telescopes_v1", True),  # /category/:slug
        ("wishlist_empty_v1", "wishlist_items_v1", False),
        ("product_2_in_v1", "product_2_v1", False),
    ],
)
def test_equivalence_table(a, b, same):
    assert (key(a) == key(b)) is same, (key(a), key(b))


def test_route_keys():
    assert route_key("http://x/product/12") == "/product/:id"
    assert route_key("http://x/search?q=lens") == "/search?q"
    assert route_key("http://x/login?next=/checkout") == "/login?next"
    assert route_key("http://x/category/maps") == "/category/:slug"
    assert route_key("http://x/") == "/"
    assert route_key("http://x/cart?notice=empty&b=1") == "/cart?b&notice"


def test_auth():
    assert key("home_in_v1").split("|")[1] == "in"
    assert key("home_out_v1").split("|")[1] == "out"
    assert key("checkout_form_v1").split("|")[1] == "in"


def test_state_count_is_small():
    """All 54 fixtures collapse to a few dozen states (50+ would mean content leaks into the hash)."""
    keys = {key(p.stem) for p in SNAPS.glob("*.json")}
    assert 15 <= len(keys) <= 40


def test_default_names():
    d = json.loads((SNAPS / "cart_empty_out_v1.json").read_text())
    assert default_name("/cart", "out", d["main"]) == "Your cart (empty)"
    d = json.loads((SNAPS / "product_2_v1.json").read_text())
    assert default_name("/product/:id", "out", d["main"]) == "Product"
    d = json.loads((SNAPS / "home_in_v1.json").read_text())
    assert default_name("/", "in", d["main"]) == "Nebula Gear (logged in)"
    d = json.loads((SNAPS / "cart_coupon_v1.json").read_text())
    assert default_name("/cart", "out", d["main"]) == "Your cart (coupon applied, with items)"
