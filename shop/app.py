"""Nebula Gear: the small astronomy store Clew tests (handoff §7, Appendix A).

Server-rendered with Jinja2, a little vanilla JS, SQLite. Release v1 or v2 is switched at runtime through the
test hooks. The planted bugs are listed (for the scorer only) in planted_bugs.yaml.
"""

from __future__ import annotations

import json
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from shop import db

HERE = Path(__file__).parent


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.ensure()
    yield


app = FastAPI(title="Nebula Gear", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")

COOKIE = "ng_session"
ROUTES = {
    "v1": [
        "/",
        "/search",
        "/search?q",
        "/category/:slug",
        "/product/:id",
        "/cart",
        "/login",
        "/login?next",
        "/checkout",
        "/order/:id",
        "/account",
        "/wishlist",
    ],
}
ROUTES["v2"] = ROUTES["v1"] + ["/gift-cards", "/cart?notice"]


# -- helpers --------------------------------------------------------------------------------------------------
def conn():
    return db.connect()


def release(c) -> str:
    return c.execute("SELECT value FROM settings WHERE key='release'").fetchone()[0]


def session_id(request: Request) -> str:
    return request.state.sid


def current_user(c, sid: str):
    row = c.execute(
        "SELECT u.id, u.email FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.id = ?", (sid,)
    ).fetchone()
    return row


def flash(c, sid: str, message: str) -> None:
    c.execute("UPDATE sessions SET flash = ? WHERE id = ?", (message, sid))


def pop_flash(c, sid: str) -> str | None:
    row = c.execute("SELECT flash FROM sessions WHERE id = ?", (sid,)).fetchone()
    if row and row[0]:
        c.execute("UPDATE sessions SET flash = NULL WHERE id = ?", (sid,))
        return row[0]
    return None


def cart_id(c, sid: str) -> int:
    row = c.execute("SELECT id FROM carts WHERE session_id = ?", (sid,)).fetchone()
    if row:
        return row[0]
    return c.execute("INSERT INTO carts (session_id) VALUES (?)", (sid,)).lastrowid


def cart_lines(c, cid: int) -> list:
    return c.execute(
        "SELECT p.id, p.name, p.price, p.on_sale, ci.qty FROM cart_items ci JOIN products p ON p.id = ci.product_id "
        "WHERE ci.cart_id = ? ORDER BY p.id",
        (cid,),
    ).fetchall()


def add_to_cart(c, sid: str, product_id: int) -> None:
    p = c.execute("SELECT stock FROM products WHERE id = ?", (product_id,)).fetchone()
    if not p or p["stock"] <= 0:
        raise HTTPException(400, "Product unavailable")
    cid = cart_id(c, sid)
    c.execute(
        "INSERT INTO cart_items VALUES (?, ?, 1) ON CONFLICT(cart_id, product_id) DO UPDATE SET qty = qty + 1",
        (cid, product_id),
    )


def totals(c, cid: int) -> dict:
    lines = cart_lines(c, cid)
    subtotal = sum((line["price"] or 0) * line["qty"] for line in lines)
    eligible = sum((line["price"] or 0) * line["qty"] for line in lines if not line["on_sale"])
    discount = 0.0
    applied = c.execute(
        "SELECT a.code, a.times_applied, k.percent FROM applied_coupons a JOIN coupons k ON k.code = a.code "
        "WHERE a.cart_id = ?",
        (cid,),
    ).fetchone()
    if applied:
        discount = round(eligible * applied["percent"] / 100 * applied["times_applied"], 2)
    return {
        "lines": lines,
        "subtotal": subtotal,
        "discount": discount,
        "total": subtotal - discount,
        "coupon": applied["code"] if applied else None,
    }


def page(request: Request, name: str, c, **ctx) -> HTMLResponse:
    sid = session_id(request)
    user = current_user(c, sid)
    cid = cart_id(c, sid)
    ctx.update(
        release=release(c),
        user=user,
        cart_count=len(cart_lines(c, cid)),
        flash=pop_flash(c, sid),
        categories=db.CATEGORIES,
    )
    return templates.TemplateResponse(request, name, ctx)


def safe_next(target: str | None) -> str:
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return "/"


# -- sessions -------------------------------------------------------------------------------------------------
@app.middleware("http")
async def browser_session(request: Request, call_next):
    """Every browser gets a session cookie. Carts and wishlists belong to the browser session, so a fresh
    browser context always starts with an empty cart (logging in keeps the session's cart)."""
    sid = request.cookies.get(COOKIE)
    c = conn()
    if not sid or not c.execute("SELECT 1 FROM sessions WHERE id = ?", (sid,)).fetchone():
        sid = secrets.token_hex(12)
        c.execute("INSERT INTO sessions (id) VALUES (?)", (sid,))
        new = True
    else:
        new = False
    c.close()
    request.state.sid = sid
    response = await call_next(request)
    if new:
        response.set_cookie(COOKIE, sid, httponly=True, samesite="lax")
    return response


# -- pages ----------------------------------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    c = conn()
    products = c.execute("SELECT * FROM products ORDER BY id").fetchall()
    return page(request, "home.html", c, products=products)


@app.get("/search", response_class=HTMLResponse)
def search(request: Request, q: str | None = None):
    c = conn()
    results = []
    if q is not None and q.strip():
        like = f"%{q.strip().lower()}%"
        results = c.execute(
            "SELECT * FROM products WHERE lower(name) LIKE ? OR category LIKE ? ORDER BY id", (like, like)
        ).fetchall()
    data = json.dumps([{"productId": r["id"], "name": r["name"]} for r in results])
    return page(request, "search.html", c, q=q, results=results, results_json=data)


@app.get("/category/{slug}", response_class=HTMLResponse)
def category(request: Request, slug: str):
    if slug not in db.CATEGORIES:
        raise HTTPException(404)
    c = conn()
    products = c.execute("SELECT * FROM products WHERE category = ? ORDER BY id", (slug,)).fetchall()
    return page(request, "category.html", c, title=db.CATEGORIES[slug], products=products)


@app.get("/product/{pid}", response_class=HTMLResponse)
def product(request: Request, pid: int):
    c = conn()
    p = c.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
    if not p:
        raise HTTPException(404)
    return page(request, "product.html", c, p=p)


@app.post("/cart/add")
def cart_add(request: Request, product_id: int = Form(...)):
    c = conn()
    add_to_cart(c, session_id(request), product_id)
    return RedirectResponse("/cart", status_code=303)


@app.post("/api/cart")
async def api_cart(request: Request):
    body = await request.json()
    c = conn()
    add_to_cart(c, session_id(request), int(body["product_id"]))
    return {"ok": True}


@app.post("/cart/remove")
def cart_remove(request: Request, product_id: int = Form(...)):
    c = conn()
    cid = cart_id(c, session_id(request))
    c.execute("DELETE FROM cart_items WHERE cart_id = ? AND product_id = ?", (cid, product_id))
    if not cart_lines(c, cid):
        c.execute("DELETE FROM applied_coupons WHERE cart_id = ?", (cid,))
    return RedirectResponse("/cart", status_code=303)


@app.get("/cart", response_class=HTMLResponse)
def cart(request: Request, notice: str | None = None):
    c = conn()
    t = totals(c, cart_id(c, session_id(request)))
    show_notice = notice == "empty" and release(c) == "v2"
    return page(request, "cart.html", c, t=t, notice=show_notice)


@app.post("/cart/coupon")
def apply_coupon(request: Request, code: str = Form("")):
    c = conn()
    sid = session_id(request)
    cid = cart_id(c, sid)
    code = code.strip()
    coupon = c.execute("SELECT * FROM coupons WHERE code = ?", (code,)).fetchone()
    lines = cart_lines(c, cid)
    if not code:
        flash(c, sid, "Enter a coupon code.")
    elif not coupon:
        flash(c, sid, "Unknown coupon code.")
    elif not coupon["active"]:
        flash(c, sid, "This coupon has expired.")
    elif not lines:
        flash(c, sid, "Your cart is empty.")
    elif coupon["excludes_sale"] and all(line["on_sale"] for line in lines):
        flash(c, sid, "Coupon not valid on sale items.")
    else:
        # Each application is counted, and the discount is percent x times applied.
        c.execute(
            "INSERT INTO applied_coupons VALUES (?, ?, 1) "
            "ON CONFLICT(cart_id) DO UPDATE SET times_applied = times_applied + 1, code = excluded.code",
            (cid, code),
        )
        flash(c, sid, f"Coupon {code} applied.")
    return RedirectResponse("/cart", status_code=303)


@app.post("/cart/coupon/remove")
def remove_coupon(request: Request):
    c = conn()
    sid = session_id(request)
    c.execute("DELETE FROM applied_coupons WHERE cart_id = ?", (cart_id(c, sid),))
    flash(c, sid, "Coupon removed.")
    return RedirectResponse("/cart", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, next: str | None = None):
    return page(request, "login.html", conn(), next=next, error=None)


@app.post("/login", response_class=HTMLResponse)
def login(request: Request, email: str = Form(""), password: str = Form(""), next: str | None = None):
    c = conn()
    user = c.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
    if not user or user["password_hash"] != db.hash_password(password):
        return page(request, "login.html", c, next=next, error="Invalid email or password.")
    sid = session_id(request)
    c.execute("UPDATE sessions SET user_id = ? WHERE id = ?", (user["id"], sid))
    c.execute("UPDATE carts SET user_id = ? WHERE session_id = ?", (user["id"], sid))
    return RedirectResponse(safe_next(next), status_code=303)


@app.post("/logout")
def logout(request: Request):
    c = conn()
    c.execute("UPDATE sessions SET user_id = NULL WHERE id = ?", (session_id(request),))
    return RedirectResponse("/", status_code=303)


@app.get("/checkout", response_class=HTMLResponse)
def checkout(request: Request):
    c = conn()
    sid = session_id(request)
    if not current_user(c, sid):
        return RedirectResponse("/login?next=" + quote("/checkout"), status_code=303)
    t = totals(c, cart_id(c, sid))
    if release(c) == "v2" and not t["lines"]:
        return RedirectResponse("/cart?notice=empty", status_code=303)
    per_item = t["subtotal"] / len(t["lines"])
    return page(request, "checkout.html", c, t=t, per_item=per_item, error=None)


@app.post("/checkout", response_class=HTMLResponse)
def place_order(request: Request, name: str = Form(""), address: str = Form(""), city: str = Form("")):
    c = conn()
    sid = session_id(request)
    user = current_user(c, sid)
    if not user:
        return RedirectResponse("/login?next=" + quote("/checkout"), status_code=303)
    cid = cart_id(c, sid)
    t = totals(c, cid)
    if not t["lines"]:
        return RedirectResponse("/cart", status_code=303)
    if not (name.strip() and address.strip() and city.strip()):
        per_item = t["subtotal"] / len(t["lines"])
        return page(request, "checkout.html", c, t=t, per_item=per_item, error="Please fill in every field.")
    oid = c.execute(
        "INSERT INTO orders (user_id, session_id, total, name, address, city) VALUES (?, ?, ?, ?, ?, ?)",
        (user["id"], sid, t["total"], name.strip()[:100], address.strip()[:200], city.strip()[:100]),
    ).lastrowid
    for line in t["lines"]:
        c.execute("INSERT INTO order_items VALUES (?, ?, ?, ?)", (oid, line["id"], line["qty"], line["price"]))
    c.execute("DELETE FROM cart_items WHERE cart_id = ?", (cid,))
    c.execute("DELETE FROM applied_coupons WHERE cart_id = ?", (cid,))
    return RedirectResponse(f"/order/{oid}", status_code=303)


@app.get("/order/{oid}", response_class=HTMLResponse)
def order(request: Request, oid: int):
    c = conn()
    user = current_user(c, session_id(request))
    o = c.execute("SELECT * FROM orders WHERE id = ?", (oid,)).fetchone()
    if not user or not o or o["user_id"] != user["id"]:
        raise HTTPException(404)
    items = c.execute(
        "SELECT p.name, oi.qty, oi.price FROM order_items oi JOIN products p ON p.id = oi.product_id "
        "WHERE oi.order_id = ?",
        (oid,),
    ).fetchall()
    return page(request, "order.html", c, o=o, items=items)


@app.get("/account", response_class=HTMLResponse)
def account(request: Request):
    c = conn()
    user = current_user(c, session_id(request))
    if not user:
        return RedirectResponse("/login?next=" + quote("/account"), status_code=303)
    # Recent orders from this browser session, like the cart (a fresh browser always sees the same account page)
    orders = c.execute(
        "SELECT * FROM orders WHERE user_id = ? AND session_id = ? ORDER BY id DESC", (user["id"], session_id(request))
    ).fetchall()
    return page(request, "account.html", c, orders=orders)


@app.get("/wishlist", response_class=HTMLResponse)
def wishlist(request: Request):
    return page(request, "wishlist.html", conn())


@app.get("/api/wishlist")
def api_wishlist(request: Request):
    c = conn()
    rows = c.execute(
        "SELECT p.id, p.name, p.image FROM wishlist w JOIN products p ON p.id = w.product_id WHERE w.owner = ? "
        "ORDER BY p.id",
        (session_id(request),),
    ).fetchall()
    return [
        {"productId": r["id"], "name": r["name"], "image": {"url": r["image"]} if r["image"] else None} for r in rows
    ]


@app.post("/wishlist/add")
def wishlist_add(request: Request, product_id: int = Form(...)):
    c = conn()
    c.execute("INSERT OR IGNORE INTO wishlist VALUES (?, ?)", (session_id(request), product_id))
    return RedirectResponse("/wishlist", status_code=303)


@app.post("/api/wishlist/remove")
async def api_wishlist_remove(request: Request):
    body = await request.json()
    c = conn()
    c.execute("DELETE FROM wishlist WHERE owner = ? AND product_id = ?", (session_id(request), int(body["product_id"])))
    return {"ok": True}


@app.get("/gift-cards", response_class=HTMLResponse)
def gift_cards(request: Request):
    c = conn()
    if release(c) != "v2":
        raise HTTPException(404)
    return page(request, "gift_cards.html", c)


@app.post("/gift-cards")
def redeem(request: Request, code: str = Form("")):
    c = conn()
    if release(c) != "v2":
        raise HTTPException(404)
    flash(c, session_id(request), "Enter a gift card code." if not code.strip() else "Invalid gift card.")
    return RedirectResponse("/gift-cards", status_code=303)


# -- test hooks (token-protected; never routed by Caddy) ---------------------------------------------------------
def _hooks_enabled() -> bool:
    return os.environ.get("SHOP_TEST_HOOKS", "true").lower() == "true"


def _check_token(request: Request) -> None:
    if not _hooks_enabled():
        raise HTTPException(404)
    token = os.environ.get("SHOP_ADMIN_TOKEN", "")
    given = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if not token or not secrets.compare_digest(given, token):
        raise HTTPException(403)


@app.get("/__version")
def version():
    if not _hooks_enabled():
        raise HTTPException(404)
    return {"release": release(conn())}


@app.post("/__release")
async def set_release(request: Request):
    _check_token(request)
    body = await request.json()
    rel = body.get("release")
    if rel not in ROUTES:
        return JSONResponse({"error": "unknown release"}, status_code=400)
    conn().execute("UPDATE settings SET value = ? WHERE key = 'release'", (rel,))
    return {"release": rel}


@app.post("/__reset")
def reset_store(request: Request):
    _check_token(request)
    db.reset("v1")
    return {"release": "v1", "reset": True}


@app.get("/__routes")
def routes(request: Request):
    _check_token(request)
    return ROUTES
