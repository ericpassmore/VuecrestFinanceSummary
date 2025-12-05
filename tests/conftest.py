"""Test configuration helpers."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on the import path so `config`/`session` can be imported.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
