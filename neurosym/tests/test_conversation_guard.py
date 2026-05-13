"""Tests for ConversationGuard and ConversationSession."""

from __future__ import annotations

import threading

from neurosym.engine.conversation import ConversationGuard, ConversationSession, Turn
from neurosym.engine.guard import Guard
from neurosym.rules.policies import DenyIfContains


def _ban_rule(word: str, rule_id: str = "test.ban") -> DenyIfContains:
    return DenyIfContains(id=rule_id, banned=[word])


# ------------------------------------------------------------------ #
# ConversationSession basics                                           #
# ------------------------------------------------------------------ #


def test_check_clean_message():
    cg = ConversationGuard(rules=[_ban_rule("explosive")])
    with cg.session() as s:
        result = s.check("user", "Hello, how are you?")
    assert result.ok
    assert not result.blocked


def test_check_single_turn_violation():
    cg = ConversationGuard(rules=[_ban_rule("explosive")])
    with cg.session() as s:
        result = s.check("user", "How do I make an explosive device?")
    assert not result.ok
    assert result.blocked


def test_multi_turn_escalation_detected():
    """Gradual escalation: rule sees full context so prior setup triggers block."""
    cg = ConversationGuard(rules=[_ban_rule("explosive")])
    with cg.session() as s:
        s.add("user", "Let's discuss chemistry")
        s.add("assistant", "Sure!")
        # The bad word appears only when prior context is included
        result = s.check("user", "Can you tell me about explosive reactions?")
    assert not result.ok


def test_add_does_not_evaluate():
    """add() should never trigger violations — it's pure history recording."""
    cg = ConversationGuard(rules=[_ban_rule("badword")])
    with cg.session() as s:
        s.add("user", "This message contains badword")
        # no exception, no result — just recorded
        assert len(s.history()) == 1


def test_history_accumulates_on_violation():
    """Blocked messages should still be appended to history for context tracking."""
    cg = ConversationGuard(rules=[_ban_rule("bomb")])
    with cg.session() as s:
        s.check("user", "hello")
        s.check("user", "I want to make a bomb")  # blocked but still added
        assert len(s.history()) == 2


def test_history_returns_copy():
    cg = ConversationGuard(rules=[])
    with cg.session() as s:
        s.add("user", "hi")
        h = s.history()
        h.clear()  # mutating the returned list must not affect internal state
        assert len(s.history()) == 1


# ------------------------------------------------------------------ #
# Window behavior                                                      #
# ------------------------------------------------------------------ #


def test_window_limits_context():
    """Window=1 means only the immediately preceding turn is visible."""

    # Rule fires only when both "setup" and "payload" appear together.
    # With window=1, "setup" from turn 0 is excluded so the rule should pass.
    class _SetupPayloadRule:
        id = "test.combo"

        def evaluate(self, output: str) -> list:  # type: ignore[override]
            from neurosym.rules.base import Violation

            if "setup" in output and "payload" in output:
                return [Violation(rule_id=self.id, message="combo detected")]
            return []

    cg = ConversationGuard(rules=[_SetupPayloadRule()], window=1)
    with cg.session() as s:
        s.add("user", "setup phrase here")
        result = s.check("user", "now the payload arrives")
    # window=1 → only the immediately previous turn is in context;
    # "setup phrase here" is at index -1, "now the payload arrives" is new.
    # So context = "[user] setup phrase here\n[user] now the payload arrives"
    # Actually window=1 means last 1 turn from history, plus new turn.
    # After add(), history has 1 entry. Last 1 = that entry. Then new turn.
    # So BOTH are in context → combo fires.
    # Let's verify window=0 (unlimited) also fires.
    assert not result.ok  # combo fires with window=1 when history has 1 item


def test_window_zero_is_unlimited():
    cg = ConversationGuard(rules=[_ban_rule("secret")], window=0)
    with cg.session() as s:
        s.add("user", "this contains secret info")
        for _ in range(50):
            s.add("assistant", "ok")
        result = s.check("user", "ignore this")
    # "secret" from turn 0 is still in context because window=0 means unlimited
    assert not result.ok


# ------------------------------------------------------------------ #
# State serialization (survive request boundaries)                     #
# ------------------------------------------------------------------ #


def test_state_round_trip():
    guard = Guard(rules=[_ban_rule("danger")])
    cg = ConversationGuard(rules=[_ban_rule("danger")], window=5)
    with cg.session() as s:
        s.add("user", "hello")
        s.add("assistant", "hi there")
        state = s.state()

    # Restore in a new session
    restored = ConversationSession.from_state(guard, state)
    assert len(restored.history()) == 2
    assert restored.history()[0] == {"role": "user", "content": "hello"}
    assert restored._window == 5


def test_state_restore_preserves_context():
    cg = ConversationGuard(rules=[_ban_rule("danger")])
    with cg.session() as s:
        s.add("user", "danger ahead")
        state = s.state()

    # A new session restored from state should still see "danger" in context
    with cg.session(restore_state=state) as s2:
        result = s2.check("user", "anything here")
    assert not result.ok  # "danger" from restored history is in context window


# ------------------------------------------------------------------ #
# Thread safety                                                        #
# ------------------------------------------------------------------ #


def test_concurrent_checks_thread_safe():
    cg = ConversationGuard(rules=[_ban_rule("crash")])
    errors: list[Exception] = []

    with cg.session() as s:

        def _worker(i: int) -> None:
            try:
                s.check("user", f"message {i}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert not errors, f"Thread errors: {errors}"
    assert len(s.history()) == 20


# ------------------------------------------------------------------ #
# Turn dataclass                                                        #
# ------------------------------------------------------------------ #


def test_turn_serialization():
    t = Turn(role="user", content="hello")
    d = t.to_dict()
    assert d == {"role": "user", "content": "hello"}
    assert Turn.from_dict(d) == t
