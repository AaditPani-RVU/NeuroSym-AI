from collections.abc import Iterable
from typing import Protocol


class LLM(Protocol):
    def generate(self, prompt: str, **kwargs) -> str: ...
    def stream(self, prompt: str, **kwargs) -> Iterable[str]: ...
