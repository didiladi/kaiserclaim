"""
Offline tests for OegkBot's meine ÖGK refund lookup.

The fixture mirrors the structure captured from the live portal on 2026-10-24
(invented data). It guards the selectors; whether the real portal still looks
like this is only known from a live run (scripts/oegk_download_refunds.py).
"""
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from workers.playwright_bot import OegkBot

_HTML = (Path(__file__).parent / "fixtures" / "oegk" / "list_page.html").read_text()


@pytest.fixture
async def page():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()
        await page.set_content(_HTML)
        yield context, page
        await browser.close()


@pytest.mark.asyncio
async def test_selectors_resolve(page):
    _, page = page
    assert await page.locator('a[id$=":wah_tab"]').count() == 1
    assert await page.locator("#vonDat").count() == 1
    assert await page.locator('input[type=submit][value="OK"]').count() == 1
    rows = page.locator("#cb_list_done [role=row]")
    assert await rows.count() == 2
    assert await rows.nth(1).locator(".cb_date").inner_text() == "27.04.2026"
    assert "62.73" in await rows.nth(1).locator(".cb_status .badge").inner_text()
    assert await rows.nth(0).locator(".cb_download a").count() == 1


@pytest.mark.asyncio
async def test_click_and_save_writes_each_pdf(page, tmp_path):
    context, page = page
    rows = page.locator("#cb_list_done [role=row]")
    bot = OegkBot()

    await bot._click_and_save(context, page, rows.nth(0).locator(".cb_download a"), tmp_path / "a.pdf")
    await bot._click_and_save(context, page, rows.nth(1).locator(".cb_download a"), tmp_path / "b.pdf")

    assert (tmp_path / "a.pdf").read_bytes() == b"%PDF-1.4 first"
    assert (tmp_path / "b.pdf").read_bytes() == b"%PDF-1.4 second"


@pytest.mark.asyncio
async def test_download_refunds_returns_unique_paths(page, tmp_path):
    context, page = page

    async def _no_navigation(self, page, since):  # the fixture page is already the list
        return None

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(OegkBot, "_open_claim_list", _no_navigation)
        paths = await OegkBot()._download_refunds(context, page, str(tmp_path), None)

    assert len(paths) == len(set(paths)) == 2
    assert [Path(p).read_bytes() for p in paths] == [b"%PDF-1.4 first", b"%PDF-1.4 second"]
