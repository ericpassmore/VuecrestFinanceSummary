"""Basic integration test for logging into the PropVivo portal."""

from __future__ import annotations

import asyncio

import pytest

from config import get_credentials
from session import LOGIN_URL, LoginError, create_browser, login


def test_login_flow_with_config_credentials():
    """Fetch the login page and attempt a real login using configured creds."""

    try:
        username, password = get_credentials()
    except RuntimeError:
        pytest.skip("Missing PROP_VIVO credentials in .env or environment.")

    async def _run():
        async with create_browser(headless=True) as (_, _, _, page):
            await page.goto(LOGIN_URL, wait_until="domcontentloaded")

            try:
                await login(page, username=username, password=password)
            except LoginError as exc:
                pytest.fail(f"Login failed or layout changed: {exc}")

            assert "login" not in page.url.lower()

    asyncio.run(_run())
