"""Thin OpenAI client wrapper for financial summaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from openai import OpenAI

from config import get_openai_api_key
from summarizer import build_summary_prompt


def _client() -> OpenAI:
    api_key = get_openai_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    return OpenAI(api_key=api_key)


def summarize_financials(
    markdown_text: str,
    period: str,
    model: str = "gpt-4.1-mini",
    legal_details: Optional[str] = None,
) -> str:
    """Send financial markdown to OpenAI and return the summary text."""

    prompt = build_summary_prompt(markdown_text, "", period, trim=False, legal_details=legal_details)

    client = _client()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user"]},
        ],
        temperature=0.3,
    )

    if resp.choices[0].message.content is None:
        return ''

    return resp.choices[0].message.content.strip()


def save_summary(summary: str, period_label: str, year: int, month: int, base_dir: Path | str = "data/summaries") -> Path:
    """Persist the summary markdown to disk."""

    target_dir = Path(base_dir) / f"{year}" / f"{month:02d}"
    target_dir.mkdir(parents=True, exist_ok=True)
    out_path = target_dir / "financial_summary.md"
    out_path.write_text(summary, encoding="utf-8")
    return out_path
