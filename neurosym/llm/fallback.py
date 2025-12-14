# neurosym/llm/fallback.py
import time
from collections.abc import Iterable

from .base import LLM


class FallbackLLM(LLM):
    """
    Try primary first (Gemini), and fall back to secondary (Ollama) on errors.
    Includes a simple circuit-breaker cooldown after repeated primary failures.
    """

    def __init__(
        self,
        primary: LLM,
        secondary: LLM,
        cooldown_sec: float = 60.0,
        max_primary_errors: int = 3,
    ):
        self.primary = primary
        self.secondary = secondary
        self.cooldown_sec = cooldown_sec
        self.max_primary_errors = max_primary_errors
        self._primary_err = 0
        self._blocked_until: float | None = None

    def _can_use_primary(self) -> bool:
        return self._blocked_until is None or time.time() >= self._blocked_until

    def _record_primary_error(self):
        self._primary_err += 1
        if self._primary_err >= self.max_primary_errors:
            self._blocked_until = time.time() + self.cooldown_sec
            self._primary_err = 0

    def _record_primary_success(self):
        self._primary_err = 0
        self._blocked_until = None

    def generate(self, prompt: str, **kwargs) -> str:
        if self._can_use_primary():
            try:
                out = self.primary.generate(prompt, **kwargs)
                self._record_primary_success()
                return out
            except Exception:
                self._record_primary_error()
        return self.secondary.generate(prompt, **kwargs)

    def stream(self, prompt: str, **kwargs) -> Iterable[str]:
        if self._can_use_primary():
            try:
                for chunk in self.primary.stream(prompt, **kwargs):
                    yield chunk
                self._record_primary_success()
                return
            except Exception:
                self._record_primary_error()
        for chunk in self.secondary.stream(prompt, **kwargs):
            yield chunk
