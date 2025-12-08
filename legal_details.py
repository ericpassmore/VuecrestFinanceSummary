"""Helpers for persisting legal details alongside monthly summaries."""

from __future__ import annotations

from pathlib import Path


def save_legal_details(summary: str, year: int, month: int, base_dir: Path | str = "data/summaries") -> Path:
    """Write the provided markdown summary to the monthly legal file."""

    target_dir = Path(base_dir) / f"{year}" / f"{month:02d}"
    target_dir.mkdir(parents=True, exist_ok=True)
    out_path = target_dir / "legal_details.md"
    out_path.write_text(summary, encoding="utf-8")
    return out_path
