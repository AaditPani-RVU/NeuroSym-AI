from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

@dataclass
class Violation:
    rule_id: str
    message: str
    meta: Optional[Dict[str, Any]] = None

class Rule(Protocol):
    id: str
    def evaluate(self, output: Any) -> List[Violation]: ...
