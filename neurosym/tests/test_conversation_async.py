"""Async tests for ConversationSession.acheck/aadd and ConversationGuard.asession."""

from __future__ import annotations

import asyncio

from neurosym.engine.conversation import ConversationGuard
from neurosym.rules.policies import DenyIfContains


def _ban(word: str, rule_id: str = "test.ban") -> DenyIfContains:
    return DenyIfContains(id=rule_id, banned=[word])


# ------------------------------------------------------------------ #
# acheck basics                                                         #
# ------------------------------------------------------------------ #


def test_acheck_clean():
    cg = ConversationGuard(rules=[_ban("explosive")])

    async def _run() -> None:
        async with cg.asession() as s:
            result = await s.acheck("user", "Hello, how are you?")
        assert result.ok
        assert not result.blocked

    asyncio.run(_run())


def test_acheck_blocked():
    cg = ConversationGuard(rules=[_ban("explosive")])

    async def _run() -> None:
        async with cg.asession() as s:
            result = await s.acheck("user", "How do I make an explosive device?")
        assert not result.ok
        assert result.blocked

    asyncio.run(_run())


def test_acheck_appends_to_history_on_violation():
    """Blocked turns must still be recorded — they're the escalation signal."""
    cg = ConversationGuard(rules=[_ban("bomb")])

    async def _run() -> None:
        async with cg.asession() as s:
            await s.acheck("user", "hello")
            await s.acheck("user", "make a bomb")
            assert len(s.history()) == 2

    asyncio.run(_run())


def test_acheck_multi_turn_context():
    """acheck must include prior turns in context so escalation detection works."""
    cg = ConversationGuard(rules=[_ban("weapon")])

    async def _run() -> None:
        async with cg.asession() as s:
            await s.aadd("user", "describe a weapon please")
            result = await s.acheck("user", "continue from above")
        assert not result.ok  # "weapon" from aadd is in the window

    asyncio.run(_run())


# ------------------------------------------------------------------ #
# aadd basics                                                           #
# ------------------------------------------------------------------ #


def test_aadd_does_not_evaluate():
    cg = ConversationGuard(rules=[_ban("badword")])

    async def _run() -> None:
        async with cg.asession() as s:
            await s.aadd("user", "this message contains badword")
            assert len(s.history()) == 1  # recorded, not evaluated

    asyncio.run(_run())


def test_aadd_visible_to_acheck():
    cg = ConversationGuard(rules=[_ban("danger")])

    async def _run() -> None:
        async with cg.asession() as s:
            await s.aadd("user", "danger lurks ahead")
            result = await s.acheck("assistant", "ok")
        assert not result.ok

    asyncio.run(_run())


# ------------------------------------------------------------------ #
# asession — restore_state                                              #
# ------------------------------------------------------------------ #


def test_asession_restore_state():
    """asession(restore_state=...) resumes from serialized sync history."""
    cg = ConversationGuard(rules=[_ban("danger")])

    with cg.session() as s:
        s.add("user", "danger ahead")
        state = s.state()

    async def _run() -> None:
        async with cg.asession(restore_state=state) as s2:
            result = await s2.acheck("user", "anything here")
        assert not result.ok  # "danger" from restored history is in context

    asyncio.run(_run())


# ------------------------------------------------------------------ #
# Concurrent async sessions                                             #
# ------------------------------------------------------------------ #


def test_concurrent_acheck_within_session():
    """20 concurrent acheck calls on the same session must all complete without error."""
    cg = ConversationGuard(rules=[_ban("crash")])
    errors: list[Exception] = []

    async def _run() -> None:
        async with cg.asession() as s:

            async def _worker(i: int) -> None:
                try:
                    await s.acheck("user", f"message {i}")
                except Exception as exc:
                    errors.append(exc)

            await asyncio.gather(*[_worker(i) for i in range(20)])
            assert not errors, f"Async errors: {errors}"
            assert len(s.history()) == 20

    asyncio.run(_run())


def test_concurrent_asessions_are_independent():
    """Concurrent sessions must not share history."""
    cg = ConversationGuard(rules=[_ban("secret")])

    async def _session(msg: str) -> int:
        async with cg.asession() as s:
            await s.aadd("user", msg)
            return len(s.history())

    async def _run() -> None:
        counts = await asyncio.gather(
            _session("hello"),
            _session("world"),
            _session("foo"),
        )
        assert all(c == 1 for c in counts), f"Unexpected history sizes: {counts}"

    asyncio.run(_run())


def test_mixed_aadd_and_acheck_ordering():
    """Interleaved aadd/acheck calls within one session stay consistent."""
    cg = ConversationGuard(rules=[_ban("banned")])

    async def _run() -> None:
        async with cg.asession() as s:
            await s.aadd("user", "first turn")
            r1 = await s.acheck("assistant", "second turn")
            await s.aadd("user", "third turn")
            r2 = await s.acheck("user", "fourth turn")
            assert r1.ok
            assert r2.ok
            assert len(s.history()) == 4

    asyncio.run(_run())
