"""Browser session helpers for interacting with the PropVivo portal."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Iterable, Optional

from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright, Browser, BrowserContext, ElementHandle, Page, Playwright

from config import get_credentials, is_headless


LOGIN_URL = "https://login.propvivo.com/login"


class LoginError(RuntimeError):
    """Raised when login fails due to invalid credentials or page changes."""


async def _first_selector(page: Page, selectors: Iterable[str]) -> str:
    """Return the first selector that exists on the page."""

    for selector in selectors:
        handle = await page.query_selector(selector)
        if handle:
            await handle.dispose()
            return selector
    raise LoginError("Login form did not render expected inputs.")


async def _query_any(page: Page, selectors: Iterable[str]) -> Optional[ElementHandle]:
    """Return the first matching element for any selector, or None."""

    for selector in selectors:
        handle = await page.query_selector(selector)
        if handle:
            return handle
    return None


@asynccontextmanager
async def create_browser(headless: Optional[bool] = None):
    """Context manager yielding (playwright, browser, context, page).

    Caller is responsible for awaiting and using the yielded objects within the
    context block. Everything is closed on exit.
    """

    play: Playwright = await async_playwright().start()
    browser: Browser = await play.chromium.launch(headless=is_headless() if headless is None else headless)
    context: BrowserContext = await browser.new_context()
    page: Page = await context.new_page()
    try:
        yield play, browser, context, page
    finally:
        # Close resources in order; ignore failures from already-closed items.
        for closer in (page.close, context.close, browser.close):
            try:
                await closer()
            except Exception:
                pass
        try:
            await play.stop()
        except Exception:
            pass


async def login(page: Page, username: Optional[str] = None, password: Optional[str] = None, timeout_ms: int = 15000) -> None:
    """Log into PropVivo using the provided page.

    Args:
        page: Playwright Page already created from create_browser().
        username: Optional override; defaults to value from config.
        password: Optional override; defaults to value from config.
        timeout_ms: How long to wait for critical steps before failing.
    """

    user = username or get_credentials()[0]
    pwd = password or get_credentials()[1]

    try:
        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=timeout_ms)

        email_selector = await _first_selector(
            page,
            (
                "input[name='username']",
                "input[name='email']",
                "input[type='email']",
            ),
        )
        password_selector = await _first_selector(
            page,
            (
                "input[name='password']",
                "input[type='password']",
            ),
        )

        await page.fill(email_selector, user)
        await page.fill(password_selector, pwd)

        login_selector = await _first_selector(
            page,
            (
                "button[type='submit']",
                "button:has-text('Log in')",
                "text=Log in",
                "text=Login",
            ),
        )

        try:
            async with page.expect_navigation(timeout=timeout_ms):
                await page.click(login_selector)
        except PlaywrightTimeout:
            # Some flows stay on the same page; still continue to post-click checks.
            await page.click(login_selector)

        try:
            await page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except PlaywrightTimeout:
            # If network stays busy, we'll still validate via URL below.
            pass

        if "login" in page.url.lower():
            # Check for visible error message before failing.
            error_el = await _query_any(page, ("text=invalid", "text=Incorrect"))
            if error_el:
                await error_el.dispose()
                raise LoginError("Login rejected: invalid credentials.")
            raise LoginError("Login likely failed: still on login page.")
    except PlaywrightTimeout as exc:
        raise LoginError("Login timed out or page layout changed.") from exc
