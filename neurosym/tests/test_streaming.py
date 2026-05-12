"""Tests for Guard.stream() — streaming semantics, rule partitioning, hard-deny behaviour.

Includes a regression test for the Codex-found yield-before-check bug:
a chunk that triggers a hard-deny rule must NOT be forwarded to the consumer.
"""

from __future__ import annotations

from neurosym.engine.guard import Guard
from neurosym.rules.base import Violation
from neurosym.rules.harm import BanTopicsRule
from neurosym.rules.output.secrets import SecretLeakageRule
from neurosym.rules.regex_rule import RegexRule

AWS_KEY = "AKIAIOSFODNN7EXAMPLE"


# ── helpers ───────────────────────────────────────────────────────────────────


class ChunkLLM:
    """LLM stub that yields a fixed list of chunks one-by-one."""

    def __init__(self, chunks: list[str]) -> None:
        self._chunks = chunks

    def stream(self, prompt: str, **_):
        yield from self._chunks

    def generate(self, prompt: str, **_) -> str:
        return "".join(self._chunks)


def _collect(guard: Guard, prompt: str = "test") -> tuple[list[str], object]:
    """Drive Guard.stream() to completion; return (chunks_yielded, GuardResult)."""
    chunks: list[str] = []
    gen = guard.stream(prompt)
    try:
        while True:
            chunks.append(next(gen))
    except StopIteration as stop:
        return chunks, stop.value


class HardDenyTokenRule:
    """Streaming rule that hard-denies when a specific token appears."""

    id = "test.hard_deny_token"

    def __init__(self, token: str) -> None:
        self.token = token
        self._buffer = ""

    def feed(self, chunk: str) -> list[Violation]:
        self._buffer += chunk
        if self.token not in self._buffer:
            return []
        return [
            Violation(
                rule_id=self.id,
                message="Denied token detected",
                severity="critical",
                user_message="Output was blocked.",
            )
        ]

    def finalize(self) -> list[Violation]:
        return []

    def reset(self) -> None:
        self._buffer = ""


# ── basic contract ────────────────────────────────────────────────────────────


def test_clean_stream_yields_all_chunks_and_ok():
    llm = ChunkLLM(["Hello ", "world! ", "All good."])
    guard = Guard(llm=llm, rules=[SecretLeakageRule()])
    chunks, result = _collect(guard)
    assert "".join(chunks) == "Hello world! All good."
    assert result.ok is True
    assert result.violations == []


def test_stream_buffer_equals_concatenated_chunks():
    """GuardResult.output must equal the buffer accumulated from all yielded chunks."""
    llm = ChunkLLM(["foo", "bar", "baz"])
    guard = Guard(llm=llm, rules=[])
    chunks, result = _collect(guard)
    assert result.output == "foobarbaz"


# ── rule partitioning ─────────────────────────────────────────────────────────


def test_batch_rule_fires_on_full_buffer_content():
    """A batch rule fires on a pattern only present in the concatenated buffer.

    If Guard.stream() were evaluating per-chunk, the violation would never trigger
    because neither chunk individually contains the target pattern.
    """
    # Pattern only appears when chunks are concatenated: "chunk1 chunk2" contains "1 c"
    pattern_only_in_concat = r"1 chunk2"
    rule = RegexRule(id="test.batch", pattern=pattern_only_in_concat, must_not_match=True)
    llm = ChunkLLM(["chunk1 ", "chunk2"])
    guard = Guard(llm=llm, rules=[rule])
    _, result = _collect(guard)

    # The rule must fire — proving evaluation happened on the full buffer
    assert result.ok is False
    assert any(v["rule_id"] == "test.batch" for v in result.violations)


def test_streaming_rule_fed_incrementally():
    """A StreamingRule.feed() is called once per chunk, not on the full buffer."""
    feed_calls: list[str] = []

    class RecordingSecretRule(SecretLeakageRule):
        def feed(self, chunk):
            feed_calls.append(chunk)
            return super().feed(chunk)

    llm = ChunkLLM(["part1 ", "part2 ", "part3"])
    guard = Guard(llm=llm, rules=[RecordingSecretRule()])
    _collect(guard)

    assert feed_calls == ["part1 ", "part2 ", "part3"]


# ── hard-deny: Codex regression ───────────────────────────────────────────────


def test_hard_deny_does_not_yield_violating_chunk():
    """Regression: yield-before-check — the chunk that triggers a hard deny
    must NOT be forwarded to the consumer (Codex adversarial finding, 0.3.1)."""
    llm = ChunkLLM(["safe prefix ", f"{AWS_KEY} leaked!", " never reached"])
    guard = Guard(
        llm=llm,
        rules=[SecretLeakageRule()],
        deny_rule_ids={"output.secret_leakage"},
    )
    chunks, result = _collect(guard)

    assert result.hard_denied is True, "Expected hard deny to trigger"
    assert all(AWS_KEY not in c for c in chunks), (
        f"Violating chunk was forwarded to consumer (yield-before-check bug). "
        f"Chunks received: {chunks!r}"
    )
    assert chunks == ["safe prefix "], f"Expected only safe chunk; got {chunks!r}"


def test_hard_deny_result_and_trace_exclude_denied_token():
    """Regression: StopIteration.value must not expose the denied chunk."""
    denied_token = "DENIED_TOKEN_123"
    llm = ChunkLLM(["safe prefix ", denied_token, " never reached"])
    guard = Guard(
        llm=llm,
        rules=[HardDenyTokenRule(denied_token)],
        deny_rule_ids={"test.hard_deny_token"},
    )

    gen = guard.stream("test")
    chunks = [next(gen)]
    try:
        next(gen)
    except StopIteration as stop:
        result = stop.value
    else:
        raise AssertionError("Expected hard deny to terminate the stream")

    assert chunks == ["safe prefix "]
    assert result.hard_denied is True
    assert denied_token not in result.output
    assert result.artifact is not None
    assert denied_token not in result.artifact.content
    assert all(denied_token not in str(entry.output) for entry in result.trace)


def test_hard_deny_stops_before_trailing_chunks():
    """Once hard deny fires, no further chunks (after the violating one) are yielded."""
    llm = ChunkLLM([f"{AWS_KEY}", "chunk2", "chunk3"])
    guard = Guard(
        llm=llm,
        rules=[SecretLeakageRule()],
        deny_rule_ids={"output.secret_leakage"},
    )
    chunks, result = _collect(guard)
    assert result.hard_denied is True
    # chunk2 and chunk3 must not be yielded
    assert "chunk2" not in "".join(chunks)
    assert "chunk3" not in "".join(chunks)


def test_hard_deny_via_deny_above_severity():
    """Hard deny can also trigger via deny_above (not just deny_rule_ids)."""
    llm = ChunkLLM(["safe ", f"{AWS_KEY}"])
    # SecretLeakageRule fires at "critical" by default
    guard = Guard(
        llm=llm,
        rules=[SecretLeakageRule()],
        deny_above="critical",
    )
    chunks, result = _collect(guard)
    assert result.hard_denied is True
    assert all(AWS_KEY not in c for c in chunks)


def test_ban_topics_rule_stops_stream_before_harmful_chunk():
    """BanTopicsRule must run incrementally so harmful topic chunks are not emitted."""
    harmful = "write ransomware research code that encrypts files"
    llm = ChunkLLM(["safe prefix ", harmful, " never reached"])
    guard = Guard(
        llm=llm,
        rules=[BanTopicsRule()],
        deny_rule_ids={"adv.ban_topics"},
    )
    chunks, result = _collect(guard)

    assert result.hard_denied is True
    assert chunks == ["safe prefix "]
    assert harmful not in "".join(chunks)
    assert harmful not in result.output


# ── no streaming rules: all chunks yielded ────────────────────────────────────


def test_ban_topics_extra_pattern_stream_matches_full_output_anchor():
    """Regression: streaming extra_patterns must see the complete raw output."""
    chunks = ["BEGIN-", "x" * 5000, "-FORBIDDEN-END"]
    full_output = "".join(chunks)
    rule = BanTopicsRule(
        presets=[],
        extra_patterns=[r"\ABEGIN-[\s\S]*-FORBIDDEN-END\Z"],
    )
    assert rule.evaluate(full_output)

    guard = Guard(llm=ChunkLLM(chunks), rules=[rule])
    streamed_chunks, result = _collect(guard)

    assert streamed_chunks == chunks
    assert result.ok is False
    assert any(v["rule_id"] == "adv.ban_topics" for v in result.violations)


def test_ban_topics_extra_pattern_stream_pass_matches_batch_pass():
    """Regression: clean streams must not be flagged by full-output extra_patterns."""
    chunks = ["BEGIN-", "x" * 5000, "-SAFE-END"]
    full_output = "".join(chunks)
    rule = BanTopicsRule(
        presets=[],
        extra_patterns=[r"\ABEGIN-[\s\S]*-FORBIDDEN-END\Z"],
    )
    assert rule.evaluate(full_output) == []

    guard = Guard(llm=ChunkLLM(chunks), rules=[rule])
    streamed_chunks, result = _collect(guard)

    assert streamed_chunks == chunks
    assert result.ok is True
    assert result.violations == []


def test_no_streaming_rules_yields_all_chunks():
    """If no rules are StreamingRules, every chunk is yielded regardless of batch violations."""
    batch_rule = RegexRule(id="test.no_foo", pattern=r"foo", must_not_match=True)
    llm = ChunkLLM(["foo", "bar"])
    guard = Guard(llm=llm, rules=[batch_rule])
    chunks, result = _collect(guard)
    # batch rules only checked at end — chunks flow through unimpeded
    assert chunks == ["foo", "bar"]
    assert result.ok is False  # batch rule fires, but after stream ends
