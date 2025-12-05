"""Shared wait utilities for PropVivo pages."""

from __future__ import annotations

from typing import Iterable

from playwright.async_api import Page, TimeoutError


async def _wait_first(page: Page, selectors: Iterable[str], timeout_ms: int) -> None:
    """Wait until any selector is visible; ignore failures until last option."""

    last_error: TimeoutError | None = None
    for selector in selectors:
        try:
            await page.wait_for_selector(selector, state="visible", timeout=timeout_ms)
            return
        except TimeoutError as exc:
            last_error = exc
    if last_error:
        raise last_error


async def wait_for_financial_table(page: Page, timeout_ms: int = 15000) -> None:
    """Wait for the financial table to load with totals visible.

    Ensures the main table exists, attempts to confirm header/toolbar presence,
    waits for subtotal/total rows, and nudges lazy-loaded content by scrolling.
    """

    await page.wait_for_selector("table.min-w-full.border-collapse", timeout=timeout_ms)

    try:
        await _wait_first(
            page,
            (
                "div[role='toolbar']",
                "button:has-text('Export')",
                "button:has-text('Print')",
                "div.tableTopData",
                "header",
            ),
            timeout_ms,
        )
    except TimeoutError:
        # Header controls may change; proceed if table exists.
        pass

    await page.wait_for_selector("table.min-w-full tbody tr.font-semibold", timeout=timeout_ms)

    # Encourage lazy-loaded rows to render, then reconfirm totals row exists.
    try:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_selector("table.min-w-full tbody tr.font-semibold", timeout=timeout_ms)
    except TimeoutError:
        pass
