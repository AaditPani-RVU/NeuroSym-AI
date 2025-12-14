# neurosym/utils/json_tools.py
from __future__ import annotations

import json
from typing import Any


def parse_json_maybe(text: Any) -> tuple[Any | None, str | None]:
    """
    Try to parse `text` as JSON if it's a string. If it's already a Python object, return it.
    Returns (obj, err) where err is None on success or a short error string on failure.
    """
    if not isinstance(text, str):
        return text, None
    try:
        return json.loads(text), None
    except Exception as e:
        return None, str(e)


def to_json_compact(obj: Any) -> str:
    """Compact JSON (no spaces) for logs or wire transfers."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def to_json_pretty(obj: Any) -> str:
    """Pretty JSON for human-facing logs/reports."""
    return json.dumps(obj, indent=2, ensure_ascii=False)
