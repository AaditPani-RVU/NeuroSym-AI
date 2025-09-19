import json, re
from typing import Any, Optional

def safe_json_loads(text: str) -> Optional[Any]:
    try:
        return json.loads(text)
    except Exception:
        return None

_JSON_BLOCK = re.compile(r"\{.*\}|\[.*\]", re.DOTALL)

def extract_first_json(text: str) -> Optional[Any]:
    """
    Find and parse the first JSON object/array in a string.
    Handy when the model adds extra prose around your JSON.
    """
    m = _JSON_BLOCK.search(text or "")
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None
