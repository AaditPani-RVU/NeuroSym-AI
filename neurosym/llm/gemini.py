# neurosym/llm/gemini.py
import os, time
from typing import Iterable, Optional
import google.generativeai as genai
from .base import LLM

class GeminiLLM(LLM):
    """
    Adapter for Google Gemini (google-generativeai).
    Supports JSON mode via response_mime_type/response_schema in generation_config.
    """
    def __init__(
        self,
        model: str = "gemini-1.5-flash",
        api_key: Optional[str] = None,
        max_retries: int = 2,
        generation_config: Optional[dict] = None,
        response_mime_type: Optional[str] = None,
        response_schema: Optional[dict] = None,
    ):
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY not set")
        genai.configure(api_key=key)

        self.model_name = model
        self.max_retries = max_retries
        self.generation_config = dict(generation_config or {})
        if response_mime_type:
            self.generation_config["response_mime_type"] = response_mime_type
        if response_schema:
            self.generation_config.setdefault("response_mime_type", "application/json")
            self.generation_config["response_schema"] = response_schema

        self._client = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=self.generation_config or None
        )

    def _call(self, prompt: str, **kwargs) -> str:
        cfg = dict(self.generation_config)
        if "temperature" in kwargs:
            cfg["temperature"] = kwargs["temperature"]
        model = self._client if cfg == self.generation_config else \
                genai.GenerativeModel(model_name=self.model_name, generation_config=cfg)

        delay = 1.0
        for attempt in range(self.max_retries + 1):
            try:
                resp = model.generate_content(prompt)
                return (getattr(resp, "text", "") or "").strip()
            except Exception:
                if attempt >= self.max_retries:
                    raise
                time.sleep(delay); delay = min(delay * 2, 8.0)
        raise RuntimeError("Gemini call failed after retries")

    def generate(self, prompt: str, **kwargs) -> str:
        return self._call(prompt, **kwargs)

    def stream(self, prompt: str, **kwargs) -> Iterable[str]:
        yield self._call(prompt, **kwargs)
