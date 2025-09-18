from typing import Any, List
from jsonschema import Draft202012Validator, ValidationError
from .base import Rule, Violation
import json

class SchemaRule:
    def __init__(self, id: str, schema: dict):
        self.id = id
        self.validator = Draft202012Validator(schema)

    def evaluate(self, output: Any) -> List[Violation]:
        data = output
        if isinstance(output, str):
            try:
                data = json.loads(output)
            except Exception:
                return [Violation(self.id, "Output is not valid JSON")]
        try:
            self.validator.validate(data)
            return []
        except ValidationError as e:
            return [Violation(self.id, f"Schema violation: {e.message}")]
