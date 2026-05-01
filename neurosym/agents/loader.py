"""Agent prompt loader — reads .md agent files from the agents/ directory."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_AGENTS_DIR = Path(__file__).parent


class AgentNotFoundError(FileNotFoundError):
    """Raised when an agent file does not exist in the agents directory."""

    def __init__(self, name: str, searched: Path) -> None:
        super().__init__(f"Agent {name!r} not found. Searched: {searched}")
        self.name = name
        self.searched = searched


class AgentLoadError(ValueError):
    """Raised when an agent file exists but its content is invalid."""

    def __init__(self, name: str, reason: str) -> None:
        super().__init__(f"Agent {name!r} could not be loaded: {reason}")
        self.name = name
        self.reason = reason


@lru_cache(maxsize=64)
def load_agent_prompt(name: str) -> str:
    """Load an agent system prompt by name.

    Reads ``<name>.md`` from the ``neurosym/agents/`` directory.
    Results are cached so repeated calls are O(1) after the first load.

    Args:
        name: Agent name without the ``.md`` extension (e.g. ``"neurosym_dev_agent"``).

    Returns:
        The full text content of the agent file.

    Raises:
        AgentNotFoundError: The file does not exist.
        AgentLoadError: The file exists but is empty or unreadable.
    """
    agent_file = (_AGENTS_DIR / name).with_suffix(".md")

    if not agent_file.exists():
        raise AgentNotFoundError(name, _AGENTS_DIR)

    try:
        content = agent_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise AgentLoadError(name, f"OS error reading file: {exc}") from exc

    stripped = content.strip()
    if not stripped:
        raise AgentLoadError(name, "file is empty")

    return stripped


def invalidate_cache() -> None:
    """Clear the in-process prompt cache (useful in tests or after hot-reloading)."""
    load_agent_prompt.cache_clear()
