from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol


class LLM(Protocol):
    def generate(self, prompt: str, **gen_kwargs: Any) -> str: ...
    def stream(self, prompt: str, **gen_kwargs: Any) -> Iterable[str]: ...
