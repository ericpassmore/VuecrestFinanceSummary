"""Integration test for navigating to the Income Statement page."""

from __future__ import annotations

import asyncio

import pytest

from config import get_credentials
from navigation import get_reporting_period, go_to_income_statement
from session import create_browser, login


def test_income_statement_page_has_content():
    """Log in and navigate to the income statement, ensuring content is present."""

    try:
        username, password = get_credentials()
    except RuntimeError:
        pytest.skip("Missing PROP_VIVO credentials in .env or environment.")

    async def _run():
        async with create_browser(headless=True) as (_, _, _, page):
            await login(page, username=username, password=password)
            await go_to_income_statement(page)

            # Validate we left the login page and see expected content.
            assert "IncomeStatement" in page.url
            content = await page.content()
            assert "Income" in content or "Statement" in content

            month_text, year_text, period_str = await get_reporting_period(page)
            assert month_text
            assert year_text.isdigit()
            assert len(period_str) == 7 and period_str[4] == "-"

    asyncio.run(_run())
