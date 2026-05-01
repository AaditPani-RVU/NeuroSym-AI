"""Agent registry — enumerate and retrieve agents from the agents/ directory."""

from __future__ import annotations

from pathlib import Path

from .loader import AgentLoadError, AgentNotFoundError, load_agent_prompt

_AGENTS_DIR = Path(__file__).parent


def list_agents() -> list[str]:
    """Return the names of all agents available on disk (no extension).

    Returns:
        Sorted list of agent names, e.g. ``["neurosym_dev_agent", "security_auditor"]``.
    """
    return sorted(p.stem for p in _AGENTS_DIR.glob("*.md"))


def agent_exists(name: str) -> bool:
    """Return ``True`` if an agent file named ``<name>.md`` exists.

    Args:
        name: Agent name without extension.
    """
    return (_AGENTS_DIR / name).with_suffix(".md").exists()


def get_agent(name: str) -> str:
    """Return the system prompt for the named agent.

    This is the primary entry-point for agent consumers.

    Args:
        name: Agent name without the ``.md`` extension.

    Returns:
        Full agent system prompt as a string.

    Raises:
        AgentNotFoundError: The agent does not exist.
        AgentLoadError: The agent file is empty or unreadable.

    Example::

        from neurosym.agents import get_agent

        prompt = get_agent("neurosym_dev_agent")
    """
    return load_agent_prompt(name)


__all__ = [
    "list_agents",
    "agent_exists",
    "get_agent",
    "AgentNotFoundError",
    "AgentLoadError",
]
