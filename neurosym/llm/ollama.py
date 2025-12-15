from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


class OllamaLLM:
    def __init__(self, model: str, base_url: str = "http://localhost:11434") -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")

    def stream(self, prompt: str, **gen_kwargs: Any) -> Iterable[str]:
        # Minimal streaming: yield full output once (satisfies Protocol).
        yield self.generate(prompt, **gen_kwargs)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4))
    def generate(self, prompt: str, **gen_kwargs: Any) -> str:
        payload: dict[str, Any] = {"model": self.model, "prompt": prompt, "stream": False}
        payload.update(gen_kwargs)

        try:
            r = httpx.post(f"{self.base_url}/api/generate", json=payload, timeout=60.0)
            r.raise_for_status()
            data: dict[str, Any] = r.json()
            resp = data.get("response", "")
            return resp.strip() if isinstance(resp, str) else ""
        except Exception as e:
            raise RuntimeError(f"OllamaLLM failed: {e}") from e
