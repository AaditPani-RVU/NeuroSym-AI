from __future__ import annotations

import json
import re
from typing import Any

from jsonschema import Draft202012Validator, SchemaError

from .base import Violation

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE | re.MULTILINE)


def _strip_fences(s: str) -> str:
    return re.sub(_FENCE_RE, "", s).strip()


def _extract_first_json_block(text: str) -> str | None:
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
                break
            top = stack.pop()
            if (top == "{" and ch != "}") or (top == "[" and ch != "]"):
                return None
            if not stack:
                return text[start : i + 1]
    return None


class SchemaRule:
    """
    Validate that output conforms to a given JSON Schema.

    - output may be a Python object, JSON string, or messy text containing JSON.
    - Emits one Violation with an 'errors' list for rich feedback.
    """

    def __init__(
        self,
        id: str,
        schema: dict[str, Any],
        *,
        extract_from_text: bool = True,
        max_errors: int = 5,
    ) -> None:
        self.id = id
        self.extract_from_text = extract_from_text
        self.max_errors = max(1, int(max_errors))
        try:
            self._validator = Draft202012Validator(schema)
        except SchemaError as e:
            raise ValueError(f"Invalid JSON Schema for {id}: {e.message}") from e

    def evaluate(self, output: Any) -> list[Violation]:
        data, parse_err = _ensure_json_any(output, extract=self.extract_from_text)
        if parse_err:
            return [Violation(rule_id=self.id, message="Output is not valid JSON", meta=parse_err)]

        # Collect multiple errors (better UX)
        errors: list[dict[str, Any]] = []
        for e in self._validator.iter_errors(data):
            errors.append(
                {
                    "path": "/".join(str(x) for x in e.path) or "$",
                    "schema_path": "/".join(str(x) for x in e.schema_path),
                    "validator": e.validator,
                    "validator_value": e.validator_value,
                    "message": e.message,
                    "instance_excerpt": _excerpt(e.instance),
                }
            )
            if len(errors) >= self.max_errors:
                break

        if not errors:
            return []

        return [
            Violation(
                rule_id=self.id,
                message="JSON failed schema validation",
                meta={"errors": errors, "error_count_shown": len(errors)},
            )
        ]


def _ensure_json_any(obj: Any, *, extract: bool) -> tuple[Any | None, dict[str, Any] | None]:
    # Already a JSON-like python value
    if isinstance(obj, dict | list | int | float | bool) or obj is None:
        return obj, None

    if isinstance(obj, str):
        s = _strip_fences(obj)
        # Try direct parse
        try:
            return json.loads(s), None
        except Exception as e1:
            if not extract:
                return None, {"reason": "json_parse_error", "error": str(e1)}
            block = _extract_first_json_block(s)
            if not block:
                return None, {"reason": "no_json_found_in_text"}
            try:
                return json.loads(block), None
            except Exception as e2:
                return None, {
                    "reason": "json_parse_error_after_extract",
                    "error": str(e2),
                }

    return None, {"reason": "not_json_compatible", "type": type(obj).__name__}


def _excerpt(value: Any, limit: int = 200) -> str:
    s = repr(value)
    return s if len(s) <= limit else s[:limit] + "…"
