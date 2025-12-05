"""Navigation helpers for authenticated PropVivo pages."""

from __future__ import annotations

from typing import Tuple

from playwright.async_api import Page, TimeoutError

from app_selectors import MONTH_SELECTOR, YEAR_SELECTOR
from waits import wait_for_financial_table


INCOME_STATEMENT_URL = "https://vuecrest.propvivo.com/Financials/IncomeStatement"
BALANCE_SHEET_URL = "https://vuecrest.propvivo.com/Financials/BalanceSheet"


async def go_to_income_statement(page: Page, timeout_ms: int = 15000) -> None:
    """Navigate to the Income Statement and wait for data to be visible."""

    await page.goto(INCOME_STATEMENT_URL, wait_until="domcontentloaded", timeout=timeout_ms)
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except TimeoutError:
        pass
    await wait_for_financial_table(page, timeout_ms)


async def go_to_balance_sheet(page: Page, timeout_ms: int = 15000) -> None:
    """Navigate to the Balance Sheet and wait for data to be visible."""

    await page.goto(BALANCE_SHEET_URL, wait_until="domcontentloaded", timeout=timeout_ms)
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except TimeoutError:
        pass
    await wait_for_financial_table(page, timeout_ms)


def _normalize_month(month_text: str) -> int:
    """Convert month text into a 1-based month integer."""

    month_lookup = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }

    key = month_text.strip().lower()
    if key.isdigit():
        month_num = int(key)
        if 1 <= month_num <= 12:
            return month_num
    if key in month_lookup:
        return month_lookup[key]
    raise ValueError(f"Unrecognized month text: {month_text!r}")


async def get_reporting_period(page: Page) -> Tuple[str, str, str]:
    """Extract reporting period from month/year controls and normalize."""

    month_text = (await page.locator(MONTH_SELECTOR).inner_text()).strip()
    year_text = (await page.locator(YEAR_SELECTOR).inner_text()).strip()

    month_num = _normalize_month(month_text)
    if not year_text.isdigit():
        raise ValueError(f"Unrecognized year text: {year_text!r}")

    period_str = f"{int(year_text):04d}-{month_num:02d}"
    return month_text, year_text, period_str
