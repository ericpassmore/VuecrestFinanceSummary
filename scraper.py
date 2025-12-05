"""Utilities to capture financial page HTML snapshots."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from bs4 import BeautifulSoup
from playwright.async_api import Page

from navigation import get_reporting_period as _nav_get_reporting_period
from waits import wait_for_financial_table


@dataclass
class FinancialPageSnapshot:
    period_label: str
    year: int
    month: int
    page_html: str
    table_html: str
    source_url: str


async def get_reporting_period(page: Page) -> Dict[str, object]:
    """Extract reporting period info using configured selectors."""

    month_text, year_text, period_str = await _nav_get_reporting_period(page)
    month = int(period_str.split("-")[1])
    year = int(year_text)
    label = f"{month_text} {year}"

    return {
        "month_name": month_text,
        "month": month,
        "year": year,
        "label": label,
        "period": period_str,
    }


def _redact_account_name(name: str, mapping: Dict[str, str], next_index: int) -> Tuple[str, int]:
    """Redact individual account names according to business rules."""

    trimmed = name.strip()
    if not trimmed:
        return name, next_index

    if "-" in trimmed:
        # Drop everything before the last dash to remove institution identifiers.
        redacted = trimmed.split("-")[-1].strip()
        return (redacted or trimmed), next_index

    if trimmed not in mapping:
        mapping[trimmed] = f"Account{next_index}"
        next_index += 1

    return mapping[trimmed], next_index


def redact_account_names(table_html: str) -> Tuple[str, Dict[str, str]]:
    """Redact account names in the ACCOUNT NAME column (if present)."""

    soup = BeautifulSoup(table_html, "html.parser")
    table = soup.find("table")
    if table is None:
        return table_html, {}

    header_cells = table.select("thead th")
    name_idx: Optional[int] = None
    for idx, th in enumerate(header_cells):
        if th.get_text(strip=True).lower() == "account name":
            name_idx = idx
            break

    if name_idx is None:
        return table_html, {}

    mapping: Dict[str, str] = {}
    next_index = 1

    tbody = table.find("tbody")
    if tbody is None:
        return table_html, {}

    for tr in tbody.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if name_idx >= len(cells):
            continue

        cell = cells[name_idx]
        redacted, next_index = _redact_account_name(cell.get_text(strip=True), mapping, next_index)
        cell.clear()
        cell.append(redacted)

    return str(table), mapping


async def get_page_html(page: Page) -> FinancialPageSnapshot:
    """Capture full page HTML and table HTML after ensuring data is loaded."""

    await wait_for_financial_table(page)
    page_html = await page.content()

    table_handle = await page.query_selector("table.min-w-full.border-collapse")
    if not table_handle:
        raise RuntimeError("Financial table not found after wait.")
    table_html = await table_handle.evaluate("node => node.outerHTML")

    report_type = _detect_report_type(page.url)

    if report_type == "income_statement":
        redacted_table_html = table_html
    else:
        redacted_table_html, _ = redact_account_names(table_html)
        if table_html in page_html:
            page_html = page_html.replace(table_html, redacted_table_html, 1)
        else:
            page_soup = BeautifulSoup(page_html, "html.parser")
            original_table = page_soup.select_one("table.min-w-full.border-collapse")
            if original_table is not None:
                original_table.replace_with(BeautifulSoup(redacted_table_html, "html.parser"))
                page_html = str(page_soup)

    period = await get_reporting_period(page)

    return FinancialPageSnapshot(
        period_label=period["label"],
        year=period["year"],
        month=period["month"],
        page_html=page_html,
        table_html=redacted_table_html,
        source_url=page.url,
    )


def save_snapshot(snapshot: FinancialPageSnapshot, report_type: str, base_dir: Path | str = "data/html") -> Path:
    """Persist snapshot HTML and metadata to disk.

    Returns the directory path where files were written.
    """

    target_dir = Path(base_dir) / report_type / f"{snapshot.year}" / f"{snapshot.month:02d}"
    target_dir.mkdir(parents=True, exist_ok=True)

    (target_dir / "page.html").write_text(snapshot.page_html, encoding="utf-8")
    (target_dir / "table.html").write_text(snapshot.table_html, encoding="utf-8")
    meta = {
        "year": snapshot.year,
        "month": snapshot.month,
        "label": snapshot.period_label,
        "source_url": snapshot.source_url,
    }
    (target_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return target_dir


def _detect_report_type(source_url: str) -> str:
    """Infer report type from the URL when possible."""

    url_lower = source_url.lower()
    if "incomestatement" in url_lower:
        return "income_statement"
    if "balancesheet" in url_lower:
        return "balance_sheet"
    return "financial_report"


def to_markdown(html: str, table_selector: Optional[str] = "table.min-w-full") -> str:
    """Convert PropVivo financial tables into Markdown."""

    soup = BeautifulSoup(html, "html.parser")

    table = soup.select_one(table_selector) if table_selector else soup.find("table")
    if table is None:
        raise ValueError(f"No <table> element found using selector: {table_selector!r}")

    headers = []
    thead = table.find("thead")
    if thead is not None:
        header_cells = thead.find_all("th")
        headers = [th.get_text(strip=True) for th in header_cells]

    body_rows = []
    tbody = table.find("tbody")
    if tbody is None:
        raise ValueError("No <tbody> found in table.")

    for tr in tbody.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        cell_texts = [td.get_text(strip=True) for td in cells]

        if headers:
            if len(cell_texts) < len(headers):
                cell_texts.extend([""] * (len(headers) - len(cell_texts)))
            elif len(cell_texts) > len(headers):
                cell_texts = cell_texts[: len(headers)]

        body_rows.append(cell_texts)

    lines = []

    if headers:
        header_line = "| " + " | ".join(headers) + " |"
        separator_line = "| " + " | ".join("---" for _ in headers) + " |"
        lines.append(header_line)
        lines.append(separator_line)

    for row in body_rows:
        line = "| " + " | ".join(row) + " |"
        lines.append(line)

    return "\n".join(lines)


def snapshot_to_markdown(snapshot: FinancialPageSnapshot, table_selector: Optional[str] = "table.min-w-full") -> Dict[str, str]:
    """Generate Markdown for a snapshot and include inferred report type."""

    report_type = _detect_report_type(snapshot.source_url)
    markdown = to_markdown(snapshot.table_html, table_selector=table_selector)

    return {
        "report_type": report_type,
        "period": snapshot.period_label,
        "markdown": markdown,
    }
