from .base import LLM
from .fallback import FallbackLLM

try:
    from .ollama import OllamaLLM
except ImportError:
    OllamaLLM = None  # type: ignore[assignment,misc]

try:
    from .gemini import GeminiLLM
except ImportError:
    GeminiLLM = None  # type: ignore[assignment,misc]

__all__ = ["LLM", "GeminiLLM", "OllamaLLM", "FallbackLLM"]
