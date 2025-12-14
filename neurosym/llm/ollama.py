# neurosym/llm/ollama.py
from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


class OllamaLLM:
    """
    Local LLM client for the Ollama runtime.
    Compatible with Guard's interface (generate(prompt) -> str).
    """

    def __init__(
        self,
        model: str = "phi3:mini",
        endpoint: str = "http://127.0.0.1:11434",
        timeout_s: int = 60,
    ):
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.timeout_s = timeout_s

    # automatic retries on transient failures
    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8)
    )
    def generate(self, prompt: str, **gen_kwargs) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": gen_kwargs.get("temperature", 0.2),
                "num_predict": gen_kwargs.get("max_tokens", 512),
            },
        }
        try:
            with httpx.Client(timeout=self.timeout_s) as client:
                r = client.post(f"{self.endpoint}/api/generate", json=payload)
                r.raise_for_status()
                data = r.json()
                return data.get("response", "").strip()
        except Exception as e:
            raise RuntimeError(f"OllamaLLM failed: {e}")
