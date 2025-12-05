"""Orchestration script to fetch financials, snapshot, and summarize."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
from typing import Optional

from config import get_credentials
from navigation import go_to_balance_sheet, go_to_income_statement
from openai_client import save_summary, summarize_financials
from scraper import FinancialPageSnapshot, get_page_html, save_snapshot, snapshot_to_markdown
from session import LoginError, create_browser, login
from waits import wait_for_financial_table


logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def fetch_report(page, navigate_fn, report_type: str) -> FinancialPageSnapshot:
    """Navigate to a report, wait for data, and capture HTML snapshot."""

    logger.info("Navigating to %s", report_type)
    await navigate_fn(page)
    await wait_for_financial_table(page)
    snapshot = await get_page_html(page)
    save_dir = save_snapshot(snapshot, report_type)
    logger.info("Saved %s snapshot to %s", report_type, save_dir)
    return snapshot


async def run(headless: Optional[bool]) -> None:
    username, password = get_credentials()

    async with create_browser(headless=headless) as (_, _, _, page):
        logger.info("Logging in as %s", username)
        try:
            await login(page, username=username, password=password)
        except LoginError as exc:
            logger.error("Login failed: %s", exc)
            raise

        income_snapshot = await fetch_report(page, go_to_income_statement, "income_statement")
        income_md_info = snapshot_to_markdown(income_snapshot)

        balance_snapshot = await fetch_report(page, go_to_balance_sheet, "balance_sheet")
        balance_md_info = snapshot_to_markdown(balance_snapshot)

        # Use period label from income (assume same for balance, but could compare).
        period_label = income_snapshot.period_label
        combined_md = f"Income Statement\n\n{income_md_info['markdown']}\n\nBalance Sheet\n\n{balance_md_info['markdown']}"

        logger.info("Requesting summary for %s", period_label)
        summary = summarize_financials(combined_md, period_label)
        out_path = save_summary(summary, period_label, income_snapshot.year, income_snapshot.month)
        logger.info("Saved summary to %s", out_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch and summarize PropVivo financials")
    parser.add_argument("--headless", dest="headless", type=str, default=None, help="Run browser headless (true/false)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    headless_val: Optional[bool]
    if args.headless is None:
        headless_val = None
    else:
        headless_val = args.headless.lower() in {"1", "true", "yes", "on"}

    asyncio.run(run(headless=headless_val))


if __name__ == "__main__":
    main()
