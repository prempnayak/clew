"""Page reader validation, merge with defaults, fact filter, and the heal matcher (handoff §10.5, §10.8)."""

from __future__ import annotations

import json
from pathlib import Path

from clew.explorer.extract import extract
from clew.explorer.locate import heal_candidate
from clew.explorer.page_reader import (
    FieldValue,
    InputCase,
    PageRead,
    ProposedAction,
    ReadContext,
    action_rows,
    deterministic_read,
    merge,
    new_facts,
    validate,
)

SNAPS = Path(__file__).parent.parent / "fixtures" / "snapshots"


def ctx(name: str) -> ReadContext:
    d = json.loads((SNAPS / f"{name}.json").read_text())
    url = "http://shop:8090" + d["url"]
    return ReadContext(url, "t", extract(d["page"], url), d["main"], d["page"], [], default_name="Page")


def test_deterministic_read_uses_codes_printed_on_the_page():
    c = ctx("cart_items_out_v1")
    read = validate(deterministic_read(c), c.candidates, 200)
    rows = action_rows("/cart|out|x", c.candidates, read, "page_reader")
    coupon = {r["input_case"]: json.loads(r["inputs"]) for r in rows if r["kind"] == "fill_submit"}
    assert coupon["valid"] == {"Coupon code": "SAVE10"} and coupon["invalid"] == {"Coupon code": "BADCODE"}
    assert any(r["label"] == "Proceed to checkout" for r in rows)


def test_validate_drops_unknown_ids_long_values_and_raw_credentials():
    c = ctx("login_next_v1")
    form = next(x for x in c.candidates if x.kind == "fill_submit")
    raw = PageRead(
        state_name="Log in",
        actions=[
            ProposedAction(candidate_id="c999", kind="click"),
            ProposedAction(
                candidate_id=form.id,
                kind="click",
                field_ids=form.field_ids,
                input_cases=[
                    InputCase(
                        case="valid",
                        values=[
                            FieldValue(field_id=form.field_ids[0], value="{{account.email}}"),
                            FieldValue(field_id=form.field_ids[1], value="{{account.password}}"),
                        ],
                    ),
                    InputCase(case="long", values=[FieldValue(field_id=form.field_ids[0], value="x" * 500)]),
                    InputCase(case="leak", values=[FieldValue(field_id=form.field_ids[0], value="{{secret}}")]),
                ],
            ),
        ],
    )
    v = validate(raw, c.candidates, 200)
    assert [a.candidate_id for a in v.actions] == [form.id]
    assert v.actions[0].kind == "fill_submit"  # the kind comes from extraction
    assert [x.case for x in v.actions[0].input_cases] == ["valid"]


def test_merge_keeps_defaults_for_candidates_the_model_skipped_mentioning():
    c = ctx("home_out_v1")
    default = validate(deterministic_read(c), c.candidates, 200)
    model = validate(
        PageRead(state_name="Home", actions=[ProposedAction(candidate_id="c1", kind="click", priority=9)]),
        c.candidates,
        200,
    )
    m = merge(model, default)
    assert m.state_name == "Home" and len(m.actions) == len(default.actions)
    assert next(a for a in m.actions if a.candidate_id == "c1").priority == 9


def test_new_facts_drops_echoes():
    given = ["Coupon code = 'SAVE10' → 'Coupon SAVE10 applied.'"]
    facts = [
        "Coupon code = 'SAVE10' → 'Coupon SAVE10 applied.'",
        "Use {{account.email}}",
        "The explorer logs in",
        "Checkout requires login",
        "Search is case-insensitive",
        "Wishlist needs no login",
    ]
    assert new_facts(facts, given) == ["Checkout requires login", "Search is case-insensitive"]


def test_heal_prefers_the_renamed_button_over_other_actions():
    d = json.loads((SNAPS / "product_2_v2.json").read_text())
    cands = extract(d["page"], "http://shop:8090" + d["url"])
    best, calls = heal_candidate("button", "Add to cart", "Cart", cands, taken={"add to wishlist"})
    assert best.name == "Add to bag" and calls == 0
    none, _ = heal_candidate("button", "Checkout now", "Cart", cands, taken={"add to wishlist"})
    assert none is None


def test_heal_ignores_sibling_cases_of_the_same_form():
    from clew.explorer.worker import names_of_other_elements

    actions = [
        {"key": "/p|out|x#form:qty:valid", "name": "buy tickets", "aliases": ["book tickets"]},  # healed already
        {"key": "/p|out|x#form:qty:invalid", "name": "book tickets", "aliases": []},
        {"key": "/p|out|x#button:save", "name": "save", "aliases": []},
    ]
    taken = names_of_other_elements(actions, {"key": "/p|out|x#form:qty:invalid", "kind": "fill_submit"})
    assert taken == {"save"}  # the healed sibling's new name is not "taken"
