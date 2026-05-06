"""Tests for agents/loader.py and agents/registry.py — 0.3.1 coverage."""

from __future__ import annotations

import pytest

from neurosym.agents.loader import (
    AgentLoadError,
    AgentNotFoundError,
    invalidate_cache,
    load_agent_prompt,
)
from neurosym.agents.registry import agent_exists, get_agent, list_agents

# ── loader ────────────────────────────────────────────────────────────────────


def test_load_agent_prompt_neurosym_dev():
    invalidate_cache()
    content = load_agent_prompt("neurosym_dev_agent")
    assert isinstance(content, str)
    assert len(content) > 0


def test_load_agent_prompt_security_auditor():
    invalidate_cache()
    content = load_agent_prompt("security_auditor")
    assert isinstance(content, str)
    assert len(content) > 0


def test_load_agent_prompt_not_found():
    invalidate_cache()
    with pytest.raises(AgentNotFoundError) as exc_info:
        load_agent_prompt("no_such_agent_xyzzy")
    assert "no_such_agent_xyzzy" in str(exc_info.value)


def test_load_agent_prompt_empty_file(tmp_path, monkeypatch):
    """AgentLoadError raised when the .md file exists but is empty."""
    import neurosym.agents.loader as loader_mod

    empty_file = tmp_path / "empty_agent.md"
    empty_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(loader_mod, "_AGENTS_DIR", tmp_path)
    invalidate_cache()

    with pytest.raises(AgentLoadError) as exc_info:
        load_agent_prompt("empty_agent")
    assert "empty" in str(exc_info.value).lower()

    monkeypatch.undo()
    invalidate_cache()


def test_load_agent_prompt_cache_returns_same_object():
    invalidate_cache()
    a = load_agent_prompt("neurosym_dev_agent")
    b = load_agent_prompt("neurosym_dev_agent")
    assert a is b, "lru_cache should return the identical object on repeated calls"


def test_invalidate_cache_forces_reload(tmp_path, monkeypatch):
    import neurosym.agents.loader as loader_mod

    agent_file = tmp_path / "reload_test.md"
    agent_file.write_text("version one", encoding="utf-8")
    monkeypatch.setattr(loader_mod, "_AGENTS_DIR", tmp_path)
    invalidate_cache()

    first = load_agent_prompt("reload_test")
    assert first == "version one"

    agent_file.write_text("version two", encoding="utf-8")
    # Without cache clear, old value would be returned
    invalidate_cache()
    second = load_agent_prompt("reload_test")
    assert second == "version two"

    monkeypatch.undo()
    invalidate_cache()


# ── registry ──────────────────────────────────────────────────────────────────


def test_list_agents_returns_known_agents():
    agents = list_agents()
    assert "neurosym_dev_agent" in agents
    assert "security_auditor" in agents


def test_list_agents_is_sorted():
    agents = list_agents()
    assert agents == sorted(agents)


def test_agent_exists_true():
    assert agent_exists("neurosym_dev_agent") is True


def test_agent_exists_false():
    assert agent_exists("definitely_not_an_agent_12345") is False


def test_get_agent_matches_load_agent_prompt():
    invalidate_cache()
    via_registry = get_agent("security_auditor")
    via_loader = load_agent_prompt("security_auditor")
    assert via_registry == via_loader


def test_get_agent_not_found_raises():
    with pytest.raises(AgentNotFoundError):
        get_agent("nonexistent_agent_abc")
