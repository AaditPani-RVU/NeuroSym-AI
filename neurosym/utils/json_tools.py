from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from importlib.resources import files
from typing import Any, cast

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE | re.MULTILINE)


@dataclass(frozen=True)
class JsonParseMeta:
    """
    Extra info about how JSON was parsed.
    """

    mode: str  # "direct" | "fence_stripped" | "extracted_block"
    extracted: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def strip_code_fences(text: str) -> str:
    return re.sub(_FENCE_RE, "", text).strip()


def extract_first_json_block(text: str) -> str | None:
    """
    Best-effort extraction of the first JSON object/array substring.
    """
    start_positions = [p for p in (text.find("{"), text.find("[")) if p != -1]
    if not start_positions:
        return None

    start = min(start_positions)
    stack: list[str] = []

    for i in range(start, len(text)):
        ch = text[i]
        if ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if not stack:
                return None
            top = stack.pop()
            if (top == "{" and ch != "}") or (top == "[" and ch != "]"):
                return None
            if not stack:
                return text[start : i + 1]

    return None


def parse_json_maybe(text: Any) -> tuple[Any | None, str | None]:
    """
    Backwards-compatible JSON parse helper.
    """
    if not isinstance(text, str):
        return text, None
    try:
        return json.loads(text), None
    except Exception as e:
        return None, str(e)


def parse_json_best_effort(text: Any) -> tuple[Any | None, JsonParseMeta]:
    """
    Product-grade JSON parsing.
    """
    if not isinstance(text, str):
        return text, JsonParseMeta(mode="direct", extracted=False)

    try:
        return json.loads(text), JsonParseMeta(mode="direct", extracted=False)
    except Exception:
        pass

    stripped = strip_code_fences(text)
    if stripped != text:
        try:
            return json.loads(stripped), JsonParseMeta(mode="fence_stripped", extracted=False)
        except Exception as e:
            last_err = str(e)
    else:
        last_err = "direct_parse_failed"

    block = extract_first_json_block(stripped)
    if not block:
        return None, JsonParseMeta(mode="extracted_block", extracted=False, error=last_err)

    try:
        return json.loads(block), JsonParseMeta(mode="extracted_block", extracted=True)
    except Exception as e:
        return None, JsonParseMeta(mode="extracted_block", extracted=True, error=str(e))


def load_schema(name: str) -> dict[str, Any]:
    filename = name if name.endswith(".json") else f"{name}.json"
    path = files("neurosym.schemas").joinpath(filename)
    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise TypeError(f"Schema {filename} must be a JSON object, got {type(data).__name__}")

    return cast(dict[str, Any], data)


def to_json_compact(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def to_json_pretty(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)


def to_json_safe(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        return repr(obj)


def safe_json_loads(text: Any) -> Any | None:
    obj, _ = parse_json_best_effort(text)
    return obj
