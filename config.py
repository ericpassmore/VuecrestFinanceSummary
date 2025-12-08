"""Configuration loader for VuecrestSummaryReport.

This module reads values from a .env-style config file once at import time
and exposes helpers for the credentials and optional settings used by the
project. Environment variables override anything found in the file so the
service can be configured in deployments without editing local files.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional, Tuple

_ENV_FILENAME = ".env"
_FALLBACK_FILENAME = ".env.example"
_KNOWN_KEYS = {
    "PROP_VIVO_USERNAME",
    "PROP_VIVO_PASSWORD",
    "OPENAI_API_KEY",
    "API_BASE_URL",
    "OUTPUT_DIR",
    "HEADLESS",
}


def _strip_quotes(value: str) -> str:
    """Remove matching single/double quotes around a value."""

    if (value.startswith("'") and value.endswith("'")) or (
        value.startswith('"') and value.endswith('"')
    ):
        return value[1:-1]
    return value


def _parse_env_file(path: Path) -> Dict[str, str]:
    """Parse a simple KEY=VALUE env file, ignoring comments/blank lines."""

    values: Dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = _strip_quotes(value.strip())
    return values


def _load_config() -> Dict[str, str]:
    """Load configuration from .env or fallback file, then overlay os.environ."""

    base_dir = Path(__file__).resolve().parent
    config: Dict[str, str] = {}

    for filename in (_ENV_FILENAME, _FALLBACK_FILENAME):
        env_path = base_dir / filename
        if env_path.exists():
            config.update(_parse_env_file(env_path))
            break

    for key in _KNOWN_KEYS:
        if key in os.environ:
            config[key] = os.environ[key]

    return config


_CONFIG = _load_config()


def reload_config() -> Dict[str, str]:
    """Reload configuration from disk and environment (mainly for tests)."""

    global _CONFIG
    _CONFIG = _load_config()
    return _CONFIG


def get_credentials() -> Tuple[str, str]:
    """Return the PROP_VIVO credentials.

    Raises:
        RuntimeError: if either username or password is missing.
    """

    username = _CONFIG.get("PROP_VIVO_USERNAME")
    password = _CONFIG.get("PROP_VIVO_PASSWORD")

    if not username or not password:
        raise RuntimeError(
            "Missing credentials. Set PROP_VIVO_USERNAME and PROP_VIVO_PASSWORD "
            "in .env or environment variables."
        )

    return username, password


def get_openai_api_key() -> Optional[str]:
    """Return the optional OpenAI API key."""

    return _CONFIG.get("OPENAI_API_KEY")


def _ensure_scheme(url: str) -> str:
    """Normalize the base URL to include a scheme and drop trailing slashes."""

    cleaned = url.strip().rstrip("/")
    if not cleaned:
        return cleaned
    if not cleaned.startswith(("http://", "https://")):
        return f"http://{cleaned}"
    return cleaned


def get_api_base_url(default_port: int | str = 8080) -> str:
    """Return the base URL used for outbound API calls.

    Falls back to localhost with the provided port when nothing is configured.
    """

    raw = _CONFIG.get("API_BASE_URL")
    if raw:
        return _ensure_scheme(raw)

    port = str(default_port).lstrip(":")
    return f"http://localhost:{port}"


def get_output_dir(default: str = "output") -> Path:
    """Return the configured output directory path (not created automatically)."""

    output_dir = _CONFIG.get("OUTPUT_DIR", default)
    return Path(output_dir).expanduser().resolve()


def is_headless(default: bool = True) -> bool:
    """Return whether browser automation should run headless."""

    raw = _CONFIG.get("HEADLESS")
    if raw is None:
        return default

    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Generic helper to retrieve arbitrary config entries."""

    if key in _CONFIG:
        return _CONFIG[key]
    return default
