"""Every planted bug and decoy behaves as specified, per release (handoff §20, Appendix A)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

TOKEN = "test-admin-token"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOP_DB", str(tmp_path / "nebula.db"))
    monkeypatch.setenv("SHOP_ADMIN_TOKEN", TOKEN)
    monkeypatch.setenv("SHOP_EXPLORER_PASSWORD", "pw")
    import importlib

    from shop import app as app_mod
    from shop import db

    importlib.reload(db)
    importlib.reload(app_mod)
    db.reset()
    with TestClient(app_mod.app, raise_server_exceptions=False) as c:
        yield c


def release(client, rel):
    r = client.post("/__release", json={"release": rel}, headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200


def login(client, next_path=None):
    url = "/login" + (f"?next={next_path}" if next_path else "")
    return client.post(url, data={"email": "explorer1@nebula.test", "password": "pw"}, follow_redirects=False)


def test_hooks_need_token(client):
    assert client.get("/__version").json() == {"release": "v1"}
    assert client.post("/__release", json={"release": "v2"}).status_code == 403
    assert client.get("/__routes").status_code == 403
    assert "/gift-cards" in client.get("/__routes", headers={"Authorization": f"Bearer {TOKEN}"}).json()["v2"]


def test_pages_render(client):
    for path in ["/", "/search", "/search?q=star", "/category/maps", "/product/1", "/cart", "/login", "/wishlist"]:
        r = client.get(path)
        assert r.status_code == 200, path
        assert '<meta name="app-release" content="v1">' in r.text


def test_b1_coupon_stacks(client):
    client.post("/cart/add", data={"product_id": 1})
    client.post("/cart/coupon", data={"code": "SAVE10"})
    assert 'data-testid="discount">12.00' in client.get("/cart").text
    client.post("/cart/coupon", data={"code": "SAVE10"})
    page = client.get("/cart").text
    assert 'data-testid="discount">24.00' in page and "Remove coupon" in page


def test_b2_empty_checkout_500_in_v1_fixed_in_v2(client):
    r = login(client, "/checkout")
    assert r.headers["location"] == "/checkout"
    assert client.get("/checkout").status_code == 500
    release(client, "v2")
    r = client.get("/checkout", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/cart?notice=empty"
    assert 'role="status"' in client.get("/cart?notice=empty").text


def test_checkout_with_items_works(client):
    login(client)
    client.post("/cart/add", data={"product_id": 2})
    assert client.get("/checkout").status_code == 200
    r = client.post("/checkout", data={"name": "A", "address": "B", "city": "C"}, follow_redirects=False)
    assert r.headers["location"].startswith("/order/")
    assert client.get(r.headers["location"]).status_code == 200


def test_checkout_requires_login(client):
    r = client.get("/checkout", follow_redirects=False)
    assert r.headers["location"] == "/login?next=/checkout"


def test_b3_product_one_has_no_image(client):
    client.post("/wishlist/add", data={"product_id": 1})
    assert client.get("/api/wishlist").json()[0]["image"] is None
    assert "No image yet" in client.get("/product/1").text


def test_b4_product_8_has_no_price_attribute(client):
    assert "data-price" not in client.get("/product/8").text
    assert 'data-price="249.00"' in client.get("/product/2").text


def test_r1_and_rename_and_gift_cards_in_v2(client):
    assert "data-index" in client.get("/search?q=star").text
    assert client.get("/gift-cards").status_code == 404
    release(client, "v2")
    page = client.get("/search?q=star").text
    assert "data-idx" in page and "data-index" not in page
    assert "Add to bag" in client.get("/product/2").text
    assert 'href="/gift-cards"' in client.get("/").text
    assert "Invalid gift card" in client.post("/gift-cards", data={"code": "SAVE10"}).text


def test_d1_out_of_stock(client):
    page = client.get("/product/9").text
    assert "disabled" in page and "Notify me" in page


def test_d2_sale_items_rejected_politely(client):
    client.post("/cart/add", data={"product_id": 5})
    page = client.post("/cart/coupon", data={"code": "SAVE10"}).text
    assert "Coupon not valid on sale items" in page and 'data-testid="discount">0.00' in page


def test_d3_no_favicon(client):
    assert client.get("/favicon.ico").status_code == 404


def test_carts_belong_to_the_browser_session(client):
    client.post("/cart/add", data={"product_id": 2})
    client.cookies.clear()
    assert "Your cart is empty" in client.get("/cart").text


def test_reset(client):
    release(client, "v2")
    client.post("/__reset", headers={"Authorization": f"Bearer {TOKEN}"})
    assert client.get("/__version").json() == {"release": "v1"}
