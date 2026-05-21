"""Tests for ConversationRule protocol — structured turn-based evaluation."""

from __future__ import annotations

import asyncio

from neurosym.engine.conversation import (
    ConversationGuard,
    ConversationRule,
    Turn,
)
from neurosym.rules.base import Violation
from neurosym.rules.policies import DenyIfContains


def _ban(word: str, rule_id: str = "test.ban") -> DenyIfContains:
    return DenyIfContains(id=rule_id, banned=[word])


# ------------------------------------------------------------------ #
# Minimal ConversationRule implementations for testing                  #
# ------------------------------------------------------------------ #


class _UserOnlyRule:
    """Fires only if a banned word appears in a user turn (not assistant)."""

    id = "test.user-only"

    def __init__(self, banned: str) -> None:
        self._banned = banned

    def evaluate_turns(self, turns: list[Turn]) -> list[Violation]:
        user_text = " ".join(t.content for t in turns if t.role == "user")
        if self._banned in user_text:
            return [Violation(rule_id=self.id, message=f"banned in user turn: {self._banned}")]
        return []


class _TurnCountRule:
    """Records which turns it received — for asserting protocol is called correctly."""

    id = "test.turn-count"
    received: list[list[Turn]]

    def __init__(self) -> None:
        self.received = []

    def evaluate_turns(self, turns: list[Turn]) -> list[Violation]:
        self.received.append(list(turns))
        return []


class _DualRule:
    """Implements both Rule and ConversationRule — tests that only evaluate_turns() is called."""

    id = "test.dual"
    text_calls: int = 0
    turn_calls: int = 0

    def evaluate(self, output: object) -> list[Violation]:
        self.text_calls += 1
        return []

    def evaluate_turns(self, turns: list[Turn]) -> list[Violation]:
        self.turn_calls += 1
        return []


# ------------------------------------------------------------------ #
# Protocol detection                                                    #
# ------------------------------------------------------------------ #


def test_conversation_rule_is_runtime_checkable():
    assert isinstance(_UserOnlyRule("x"), ConversationRule)


def test_plain_rule_is_not_conversation_rule():
    assert not isinstance(_ban("x"), ConversationRule)


# ------------------------------------------------------------------ #
# evaluate_turns receives list[Turn], not flat text                     #
# ------------------------------------------------------------------ #


def test_evaluate_turns_receives_turn_objects():
    tracker = _TurnCountRule()
    cg = ConversationGuard(rules=[tracker])

    with cg.session() as s:
        s.add("user", "hello")
        s.check("assistant", "world")

    assert len(tracker.received) == 1
    turns = tracker.received[0]
    assert all(isinstance(t, Turn) for t in turns)
    assert turns[0].role == "user"
    assert turns[0].content == "hello"
    assert turns[1].role == "assistant"
    assert turns[1].content == "world"


def test_evaluate_turns_respects_window():
    tracker = _TurnCountRule()
    cg = ConversationGuard(rules=[tracker], window=2)

    with cg.session() as s:
        s.add("user", "turn 0")
        s.add("user", "turn 1")
        s.add("user", "turn 2")
        s.check("user", "turn 3")  # window=2 → prior=[turn2, turn3... wait

    # window=2 → last 2 from history (turns 1 and 2) + new turn (turn 3)
    assert len(tracker.received[0]) == 3


# ------------------------------------------------------------------ #
# Role filtering — the primary ConversationRule use case                #
# ------------------------------------------------------------------ #


def test_user_only_rule_ignores_assistant_turns():
    rule = _UserOnlyRule("secret")
    cg = ConversationGuard(rules=[rule])

    with cg.session() as s:
        # "secret" appears only in an assistant turn → should NOT fire
        s.add("assistant", "Here is the secret")
        result = s.check("user", "thanks")

    assert result.ok


def test_user_only_rule_fires_on_user_turn():
    rule = _UserOnlyRule("forbidden")
    cg = ConversationGuard(rules=[rule])

    with cg.session() as s:
        result = s.check("user", "I want to do something forbidden")

    assert not result.ok
    assert result.blocked
    assert any("test.user-only" in v.get("rule_id", "") for v in result.violations)


# ------------------------------------------------------------------ #
# Violations merged into GuardResult                                    #
# ------------------------------------------------------------------ #


def test_conv_violations_appear_in_result_violations():
    rule = _UserOnlyRule("explosive")
    cg = ConversationGuard(rules=[rule])

    with cg.session() as s:
        result = s.check("user", "how to make an explosive")

    assert not result.ok
    assert len(result.violations) == 1
    assert result.violations[0]["rule_id"] == "test.user-only"


def test_text_rule_and_conv_rule_violations_combine():
    """Both a text Rule and a ConversationRule can fire on the same check."""
    text_rule = _ban("bomb", "test.text")
    conv_rule = _UserOnlyRule("bomb")
    cg = ConversationGuard(rules=[text_rule, conv_rule])

    with cg.session() as s:
        result = s.check("user", "make a bomb")

    assert not result.ok
    rule_ids = {v["rule_id"] for v in result.violations}
    assert "test.text" in rule_ids
    assert "test.user-only" in rule_ids


def test_text_rule_still_works_without_conv_rules():
    """Existing text-only Guard behaviour is unchanged by 0.4.3."""
    cg = ConversationGuard(rules=[_ban("danger")])

    with cg.session() as s:
        result = s.check("user", "this is dangerous")

    assert not result.ok


# ------------------------------------------------------------------ #
# Dual-protocol rules — ConversationRule path takes precedence          #
# ------------------------------------------------------------------ #


def test_dual_rule_uses_evaluate_turns_not_evaluate():
    dual = _DualRule()
    cg = ConversationGuard(rules=[dual])  # type: ignore[list-item]

    with cg.session() as s:
        s.check("user", "hello")

    assert dual.turn_calls == 1
    assert dual.text_calls == 0, "evaluate() must not be called when evaluate_turns() is available"


# ------------------------------------------------------------------ #
# async acheck also runs ConversationRule                               #
# ------------------------------------------------------------------ #


def test_acheck_runs_conv_rules():
    rule = _UserOnlyRule("forbidden")
    cg = ConversationGuard(rules=[rule])

    async def _run() -> None:
        async with cg.asession() as s:
            result = await s.acheck("user", "something forbidden here")
        assert not result.ok
        assert any("test.user-only" in v.get("rule_id", "") for v in result.violations)

    asyncio.run(_run())


# ------------------------------------------------------------------ #
# from_state preserves conv_rules                                       #
# ------------------------------------------------------------------ #


def test_from_state_preserves_conv_rules():
    rule = _UserOnlyRule("danger")
    cg = ConversationGuard(rules=[rule])

    with cg.session() as s:
        s.add("user", "danger ahead")
        state = s.state()

    with cg.session(restore_state=state) as s2:
        result = s2.check("user", "anything")

    assert not result.ok  # "danger" from restored history → user turn → fires


# ------------------------------------------------------------------ #
# Export contract                                                        #
# ------------------------------------------------------------------ #


def test_top_level_exports():
    import neurosym

    assert hasattr(neurosym, "ConversationRule")
    assert hasattr(neurosym, "Turn")
    assert neurosym.ConversationRule is ConversationRule
    assert neurosym.Turn is Turn
