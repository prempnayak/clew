"""Capture ARIA snapshot fixtures of every Nebula Gear page (handoff §10.10).

Usage (store running on SHOP_URL with SHOP_ADMIN_TOKEN):
    uv run python -m tests.fixtures.capture_snapshots
Writes tests/fixtures/snapshots/<name>.json with the URL, release, whole-page and `main` snapshots.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

SHOP = os.environ.get("SHOP_URL", "http://localhost:8090")
TOKEN = os.environ.get("SHOP_ADMIN_TOKEN", "devtoken")
PASSWORD = os.environ.get("SHOP_EXPLORER_PASSWORD", "pw")
OUT = Path(__file__).parent / "snapshots"


async def save(page, name: str, release: str) -> None:
    await page.wait_for_load_state("networkidle")
    data = {
        "url": page.url.replace(SHOP, ""),
        "release": release,
        "page": await page.aria_snapshot(),
        "main": await page.locator("main").aria_snapshot(),
    }
    (OUT / f"{name}.json").write_text(json.dumps(data, indent=1) + "\n")


async def login(page) -> None:
    await page.goto(f"{SHOP}/login")
    await page.get_by_role("textbox", name="Email").fill("explorer1@nebula.test")
    await page.get_by_role("textbox", name="Password").fill(PASSWORD)
    await page.get_by_role("button", name="Log in").click()
    await page.wait_for_load_state("networkidle")


async def capture(browser, release: str) -> None:
    sfx = f"_{release}"
    ctx = await browser.new_context()
    page = await ctx.new_page()
    simple = {
        "home_out": "/", "search_blank": "/search", "search_telescope": "/search?q=telescope", "search_star": "/search?q=star",
        "search_none": "/search?q=zzzz", "category_maps": "/category/maps", "category_telescopes":
        "/category/telescopes", "product_1": "/product/1", "product_2": "/product/2", "product_7": "/product/7",
        "product_8": "/product/8", "product_9": "/product/9", "cart_empty_out": "/cart", "login": "/login",
        "login_next": "/login?next=/checkout", "wishlist_empty": "/wishlist",
    }
    if release == "v2":
        simple["gift_cards"] = "/gift-cards"
        simple["cart_notice"] = "/cart?notice=empty"
    for name, path in simple.items():
        await page.goto(SHOP + path)
        await save(page, name + sfx, release)
    # cart with items, then coupon applied (and the flash message shown once)
    await page.goto(f"{SHOP}/product/1")
    await page.get_by_role("button", name="Add to bag" if release == "v2" else "Add to cart").click()
    await save(page, "cart_items_out" + sfx, release)
    await page.get_by_role("textbox", name="Coupon code").fill("SAVE10")
    await page.get_by_role("button", name="Apply").click()
    await save(page, "cart_coupon_flash" + sfx, release)
    await page.goto(f"{SHOP}/cart")
    await save(page, "cart_coupon" + sfx, release)
    await page.goto(f"{SHOP}/product/3")
    await page.get_by_role("button", name="Add to bag" if release == "v2" else "Add to cart").click()
    await save(page, "cart_coupon_two_items" + sfx, release)
    await page.goto(f"{SHOP}/product/2")
    await page.get_by_role("button", name="Add to wishlist").click()
    await save(page, "wishlist_items" + sfx, release)
    await ctx.close()

    ctx = await browser.new_context()
    page = await ctx.new_page()
    await login(page)
    await save(page, "home_in" + sfx, release)
    await page.goto(f"{SHOP}/cart")
    await save(page, "cart_empty_in" + sfx, release)
    await page.goto(f"{SHOP}/product/2")
    await save(page, "product_2_in" + sfx, release)
    await page.get_by_role("button", name="Add to bag" if release == "v2" else "Add to cart").click()
    await page.goto(f"{SHOP}/checkout")
    await save(page, "checkout_form" + sfx, release)
    await page.goto(f"{SHOP}/account")
    await save(page, "account" + sfx, release)
    await ctx.close()


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    headers = {"Authorization": f"Bearer {TOKEN}"}
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for release in ("v1", "v2"):
            httpx.post(f"{SHOP}/__reset", headers=headers).raise_for_status()
            httpx.post(f"{SHOP}/__release", headers=headers, json={"release": release}).raise_for_status()
            await capture(browser, release)
        await browser.close()
    httpx.post(f"{SHOP}/__reset", headers=headers).raise_for_status()
    print(f"wrote {len(list(OUT.glob('*.json')))} fixtures to {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
