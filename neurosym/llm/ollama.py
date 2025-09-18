# neurosym/llm/ollama.py
import os, time, requests, json
from typing import Iterable, Optional
from .base import LLM

class OllamaLLM(LLM):
    def __init__(self, model: str = "llama3:8b", host: Optional[str] = None,
                 timeout: float = 30.0, max_retries: int = 2):
        self.model = model
        self.host = host or os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        self.timeout = timeout
        self.max_retries = max_retries

    def _payload(self, prompt: str, **kwargs):
        temperature = kwargs.pop("temperature", 0.7)
        return {"model": self.model, "prompt": prompt, "options": {"temperature": temperature}}

    def generate(self, prompt: str, **kwargs) -> str:
        url = f"{self.host}/api/generate"
        payload = self._payload(prompt, **kwargs)
        delay = 1.0
        for attempt in range(self.max_retries + 1):
            try:
                r = requests.post(url, json=payload, timeout=self.timeout, stream=True)
                r.raise_for_status()
                out = []
                for line in r.iter_lines():
                    if not line: continue
                    obj = json.loads(line.decode("utf-8"))
                    if "response" in obj: out.append(obj["response"])
                return "".join(out)
            except (requests.Timeout, requests.ConnectionError, requests.HTTPError):
                if attempt >= self.max_retries: raise
                time.sleep(delay); delay = min(delay * 2, 8.0)
        raise RuntimeError("Ollama call failed after retries")

    def stream(self, prompt: str, **kwargs) -> Iterable[str]:
        yield self.generate(prompt, **kwargs)
