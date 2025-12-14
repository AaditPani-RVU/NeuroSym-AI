# neurosym/rules/schema_rule.py
from __future__ import annotations

import json
from typing import Any

from jsonschema import (
    Draft202012Validator,
    SchemaError,
    ValidationError,
)  # pip install jsonschema

from .base import Violation


class SchemaRule:  # implements Rule
    """
    Validate that `output` is a JSON object conforming to the given JSON Schema.
    - `output` may be a dict or a JSON string.
    - On errors, emits a single Violation with rich meta (path, validator, instance).
    """

    def __init__(self, id: str, schema: dict[str, Any]) -> None:
        self.id = id
        try:
            self._validator = Draft202012Validator(schema)
        except SchemaError as e:
            # Surface schema problems early with a clear message.
            raise ValueError(f"Invalid JSON Schema for {id}: {e.message}") from e

    def evaluate(self, output: Any) -> list[Violation]:
        data, parse_err = _ensure_json(output)
        if parse_err:
            return [
                Violation(
                    rule_id=self.id, message="Output is not valid JSON", meta=parse_err
                )
            ]

        try:
            self._validator.validate(data)
            return []
        except ValidationError as e:
            return [
                Violation(
                    rule_id=self.id,
                    message="JSON failed schema validation",
                    meta={
                        "path": "/".join(str(x) for x in e.path) or "$",
                        "schema_path": "/".join(str(x) for x in e.schema_path),
                        "validator": e.validator,
                        "validator_value": e.validator_value,
                        "message": e.message,
                        "instance_excerpt": _excerpt(e.instance),
                    },
                )
            ]


def _ensure_json(obj: Any) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """
    Try to coerce obj into a JSON object (dict). Return (data, err_meta).
    err_meta is None on success, or a small dict describing the parse issue.
    """
    if isinstance(obj, dict):
        return obj, None
    try:
        data = json.loads(obj)
        if not isinstance(data, dict):
            return None, {"reason": "not_an_object", "type": type(data).__name__}
        return data, None
    except Exception as e:
        return None, {"reason": "json_parse_error", "error": str(e)}


def _excerpt(value: Any, limit: int = 200) -> str:
    s = repr(value)
    return s if len(s) <= limit else s[:limit] + "…"
