"""Candidate extraction on the real store snapshots (handoff §10.4)."""

from __future__ import annotations

import json
from pathlib import Path

from clew.explorer.extract import extract, in_scope, messages, normalize, page_text

SNAPS = Path(__file__).parent.parent / "fixtures" / "snapshots"


def cands(name: str):
    d = json.loads((SNAPS / f"{name}.json").read_text())
    return {c.identity: c for c in extract(d["page"], "http://shop:8090" + d["url"])}


def test_link_groups_and_forms_on_home():
    c = cands("home_out_v1")
    assert c["link:/product/:id"].count == 12 and c["link:/product/:id"].region == "main"
    assert c["link:/category/:slug"].count == 3
    form = c["form:search"]
    assert form.kind == "fill_submit" and form.name == "Search" and len(form.field_ids) == 1
    assert c["link:/login"].region == "nav"


def test_login_form_groups_both_fields():
    form = cands("login_next_v1")["form:email+password"]
    assert form.name == "Log in" and len(form.field_ids) == 2


def test_disabled_buttons_are_not_candidates():
    c = cands("product_9_v1")
    assert "button:add to cart" not in c and "button:notify me" in c


def test_identity_ignores_counts_and_renames_change_names():
    assert "link:/cart" in cands("cart_coupon_v1")  # "Cart (1)" is still the /cart link
    assert "button:add to bag" in cands("product_2_v2") and "button:add to cart" in cands("product_2_v1")
    assert "link:/gift-cards" in cands("home_out_v2") and "link:/gift-cards" not in cands("home_out_v1")


def test_scope():
    assert in_scope("/cart", "http://shop:8090/") == "http://shop:8090/cart"
    assert in_scope("https://evil.example/x", "http://shop:8090/") is None
    assert in_scope("/__reset", "http://shop:8090/") is None
    assert in_scope("mailto:a@b.c", "http://shop:8090/") is None


def test_text_helpers():
    d = json.loads((SNAPS / "cart_coupon_flash_v1.json").read_text())
    assert "SAVE10" in page_text(d["page"])
    assert messages(d["main"]) == ["Coupon SAVE10 applied."]
    assert normalize("Cart (12)") == "cart (#)"
