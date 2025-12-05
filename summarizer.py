"""Prompt builder for summarizing financials via OpenAI or similar models."""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional


def _extract_relevant_lines(markdown: str, keywords: Iterable[str], max_lines: int = 200) -> str:
    """Return lines containing any keyword (case-insensitive), capped for brevity."""

    lowered_keywords = [kw.lower() for kw in keywords]
    selected: List[str] = []
    for line in markdown.splitlines():
        plain = line.lower()
        if any(kw in plain for kw in lowered_keywords):
            selected.append(line)
        if len(selected) >= max_lines:
            break
    return "\n".join(selected)


def build_summary_prompt(md_income: str, md_balance: str, period: str, trim: bool = True) -> Dict[str, str]:
    """Construct a structured prompt for summarizing HOA financials.

    Assumes the Income Statement and Balance Sheet are aggregated by major category.
    HOA income comes primarily from a single annual assessment.
    """

    legal_keywords = ("legal", "attorney", "law", "counsel")
    income_legal = _extract_relevant_lines(md_income, legal_keywords) if trim else ""
    balance_legal = _extract_relevant_lines(md_balance, legal_keywords) if trim else ""

    system_msg = (
        "You are a senior financial analyst preparing a plain-English summary for HOA homeowners. "
        "The HOA collects most income via a single annual assessment, so your focus is on spend "
        "and budget tracking over the year rather than recurring monthly income. "
        "Your job is to interpret the financial statements, identify trends, and communicate clearly. "
        "Do not make up numbers that are not present in the tables. If a value is missing, state that it "
        "is not available. Your output must always include, as the final section, a summary of all legal spend."
    )

    user_parts = [
        f"Period: {period}",
        "## TASK\n"
        "The Income Statement and Balance Sheet provided below are already aggregated by major category "
        "(for example: Assets, Liabilities, Owners’ Equity, major revenue and expense groupings).\n\n"
        "Assume HOA income primarily comes from a single annual `Assessment Revenue` event. "
        "Using ONLY these aggregated views, provide a clear, plain-English financial summary that includes:\n"
        "1. A summary of **monthly spend** and **monthly income against budget** for the period.\n"
        "   - Focus on how current-month expenses compare to the monthly or year-to-date budget.\n"
        "2. Commentary on the **largest expense categories** for the month.\n"
        "   - Show at least three categories.\n"
        "   - Show at most five categories.\n"
        "   - Only show categories when the monthly spend exceeds 5% of the category’s year-to-date budget (for example, a column labeled YTD Budget or YTD BUDGET PERIOD).\n"
        "   - If fewer than three categories exceed 5% of the YTD Budget Period, show all that meet the threshold and explicitly note that there are fewer than three.\n"
        "3. A summary comparing **actual balances against the budget** at the major-category level.\n"
        "4. An assessment of whether **current funding is sufficient to meet forecasted spend for the year**.\n"
        "   - Provide a confidence rating: High / Medium / Low and explain your reasoning.\n"
        "5. Compute and report the percentage of `Assessment Revenue` **YTD** against its `Annual Budget`:\n"
        "   - Identify the line(s) for `Assessment Revenue` (YTD and Annual Budget).\n"
        "   - Report `Assessment Revenue YTD / Assessment Revenue Annual Budget` as a percentage.\n"
        "   - Comment on whether this is ahead of, on track with, or behind expectations.\n"
        "6. Check whether `Delinquent Assessment Revenue` exceeds **4%** of the `Assessment Revenue` `Annual Budget`:\n"
        "   - If `Delinquent Assessment Revenue > 4% of Assessment Revenue Annual Budget`, "
        "explicitly call this out as a concern and briefly explain the risk.\n"
        "   - If it is at or below 4%, state that it is within acceptable bounds.\n"
        "7. Summarize monthly spend from `Total Reserve Expenditure`\n"
        "   - when there is no spend explicitly state no spending this month\n"
        "8. You must comment on legal fees and legal spend (or the absence of it).\n"
        "   - Always place the **Legal Spend Summary** as the final section of the output.\n\n"
        "When referencing these specific lines, look for labels containing:\n"
        "- `Assessment Revenue`\n"
        "- `Delinquent Assessment Revenue`\n"
        "- `YTD`\n"
        "- `Annual Budget`\n",
        "## Income Statement (Markdown, aggregated by major category)\n" + md_income,
    ]

    if md_balance:
        user_parts.append(
            "## Balance Sheet (Markdown, aggregated by major category)\n" + md_balance
        )

    if trim and (income_legal or balance_legal):
        legal_section = ["## Pre-filtered Legal Line Items (for emphasis)"]
        if income_legal:
            legal_section.append("### Income Statement Legal Lines\n" + income_legal)
        if balance_legal:
            legal_section.append("### Balance Sheet Legal Lines\n" + balance_legal)
        user_parts.append("\n".join(legal_section))

    user_msg = "\n\n".join(part for part in user_parts if part)

    return {"system": system_msg, "user": user_msg}



