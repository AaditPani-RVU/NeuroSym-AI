"""Tests for ImpactAgent.hypothesize().

All tests mock Guard.generate() to avoid requiring a live LLM.
The core contract being verified: failure modes ALWAYS raise
ImpactForecastUnavailable — they never silently return [].
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from neurosym.agents.impact_forecaster import ImpactForecastUnavailable, ImpactHypothesis
from neurosym.agents.impact_forecaster.agent import ImpactAgent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_HYPOTHESIS = {"area": "auth", "reason": "Changed auth flow", "confidence": 0.8}
_VALID_OUTPUT = json.dumps([_VALID_HYPOTHESIS])


def _make_agent() -> ImpactAgent:
    return ImpactAgent(llm=MagicMock())


def _mock_guard(ok: bool, output: object) -> MagicMock:
    """Return a context-manager-compatible patch for Guard that yields a
    mock Guard instance whose generate() returns the given result."""
    mock_result = MagicMock()
    mock_result.ok = ok
    mock_result.output = output

    mock_guard_instance = MagicMock()
    mock_guard_instance.generate.return_value = mock_result

    mock_guard_cls = MagicMock(return_value=mock_guard_instance)
    return mock_guard_cls


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


class TestHypothesizeHappyPath:
    def test_returns_list_of_hypotheses(self) -> None:
        agent = _make_agent()
        with patch(
            "neurosym.agents.impact_forecaster.agent.Guard",
            _mock_guard(ok=True, output=_VALID_OUTPUT),
        ):
            result = agent.hypothesize("Changed auth middleware")

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], ImpactHypothesis)

    def test_hypothesis_fields_are_correct(self) -> None:
        agent = _make_agent()
        with patch(
            "neurosym.agents.impact_forecaster.agent.Guard",
            _mock_guard(ok=True, output=_VALID_OUTPUT),
        ):
            result = agent.hypothesize("Changed auth middleware")

        h = result[0]
        assert h.area == "auth"
        assert h.reason == "Changed auth flow"
        assert h.confidence == pytest.approx(0.8)

    def test_multiple_hypotheses_returned(self) -> None:
        payload = json.dumps(
            [
                {"area": "auth", "reason": "auth change", "confidence": 0.9},
                {"area": "billing", "reason": "billing hook touched", "confidence": 0.6},
            ]
        )
        agent = _make_agent()
        with patch(
            "neurosym.agents.impact_forecaster.agent.Guard",
            _mock_guard(ok=True, output=payload),
        ):
            result = agent.hypothesize("Touched auth and billing modules")

        assert len(result) == 2
        areas = {h.area for h in result}
        assert areas == {"auth", "billing"}

    def test_empty_list_is_valid_no_impact_response(self) -> None:
        """LLM returning [] is a valid 'no impact found' signal, not a failure."""
        agent = _make_agent()
        with patch(
            "neurosym.agents.impact_forecaster.agent.Guard",
            _mock_guard(ok=True, output="[]"),
        ):
            result = agent.hypothesize("Whitespace-only change")

        assert result == []

    def test_accepts_already_parsed_python_list(self) -> None:
        """result.output may already be a parsed Python list (not a JSON string)."""
        agent = _make_agent()
        parsed_output = [{"area": "db", "reason": "schema change", "confidence": 0.75}]
        with patch(
            "neurosym.agents.impact_forecaster.agent.Guard",
            _mock_guard(ok=True, output=parsed_output),
        ):
            result = agent.hypothesize("Modified DB schema")

        assert len(result) == 1
        assert result[0].area == "db"

    def test_accepts_json_wrapped_in_markdown_fence(self) -> None:
        fenced = f"```json\n{_VALID_OUTPUT}\n```"
        agent = _make_agent()
        with patch(
            "neurosym.agents.impact_forecaster.agent.Guard",
            _mock_guard(ok=True, output=fenced),
        ):
            result = agent.hypothesize("Changed auth middleware")

        assert len(result) == 1


# ---------------------------------------------------------------------------
# Failure-path tests — must ALWAYS raise, never return []
# ---------------------------------------------------------------------------


class TestHypothesizeFailurePaths:
    def test_guard_failure_raises_unavailable(self) -> None:
        """result.ok = False → ImpactForecastUnavailable, not []."""
        agent = _make_agent()
        with (
            patch(
                "neurosym.agents.impact_forecaster.agent.Guard",
                _mock_guard(ok=False, output="not valid json"),
            ),
            pytest.raises(ImpactForecastUnavailable),
        ):
            agent.hypothesize("some diff")

    def test_guard_failure_never_returns_empty_list(self) -> None:
        """Regression: the old code silently returned [] on failure."""
        agent = _make_agent()
        raised = False
        try:
            with patch(
                "neurosym.agents.impact_forecaster.agent.Guard",
                _mock_guard(ok=False, output="bad"),
            ):
                result = agent.hypothesize("some diff")
                # If we reach here without raising, the result must not be []
                assert result != [], (
                    "ImpactAgent returned [] on failure — indistinguishable from 'no impact found'"
                )
        except ImpactForecastUnavailable:
            raised = True
        assert raised, "Expected ImpactForecastUnavailable to be raised on guard failure"

    def test_unparseable_output_raises_unavailable(self) -> None:
        """result.ok = True but output is garbage JSON → ImpactForecastUnavailable."""
        agent = _make_agent()
        with (
            patch(
                "neurosym.agents.impact_forecaster.agent.Guard",
                _mock_guard(ok=True, output="this is not json at all !!!"),
            ),
            pytest.raises(ImpactForecastUnavailable),
        ):
            agent.hypothesize("some diff")

    def test_schema_mismatch_raises_unavailable(self) -> None:
        """Valid JSON but wrong schema (missing required fields) → ImpactForecastUnavailable."""
        bad_output = json.dumps([{"area": "auth"}])  # missing 'reason' and 'confidence'
        agent = _make_agent()
        with (
            patch(
                "neurosym.agents.impact_forecaster.agent.Guard",
                _mock_guard(ok=True, output=bad_output),
            ),
            pytest.raises(ImpactForecastUnavailable),
        ):
            agent.hypothesize("some diff")

    def test_object_instead_of_array_raises_unavailable(self) -> None:
        """LLM returns a dict instead of a list → ImpactForecastUnavailable."""
        wrong_type = json.dumps({"area": "auth", "reason": "x", "confidence": 0.5})
        agent = _make_agent()
        with (
            patch(
                "neurosym.agents.impact_forecaster.agent.Guard",
                _mock_guard(ok=True, output=wrong_type),
            ),
            pytest.raises(ImpactForecastUnavailable),
        ):
            agent.hypothesize("some diff")

    def test_unavailable_has_reason_attribute(self) -> None:
        agent = _make_agent()
        with patch(
            "neurosym.agents.impact_forecaster.agent.Guard",
            _mock_guard(ok=False, output="bad"),
        ):
            with pytest.raises(ImpactForecastUnavailable) as exc_info:
                agent.hypothesize("some diff")

        assert hasattr(exc_info.value, "reason")
        assert isinstance(exc_info.value.reason, str)
        assert len(exc_info.value.reason) > 0

    def test_unavailable_message_is_informative(self) -> None:
        agent = _make_agent()
        with patch(
            "neurosym.agents.impact_forecaster.agent.Guard",
            _mock_guard(ok=False, output="bad"),
        ):
            with pytest.raises(ImpactForecastUnavailable) as exc_info:
                agent.hypothesize("some diff")

        assert "ImpactForecaster unavailable" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Export contract
# ---------------------------------------------------------------------------


class TestExports:
    def test_unavailable_exported_from_forecaster_package(self) -> None:
        from neurosym.agents.impact_forecaster import ImpactForecastUnavailable as IFU

        assert IFU is ImpactForecastUnavailable

    def test_unavailable_exported_from_top_level(self) -> None:
        from neurosym import ImpactForecastUnavailable as IFU

        assert IFU is ImpactForecastUnavailable
