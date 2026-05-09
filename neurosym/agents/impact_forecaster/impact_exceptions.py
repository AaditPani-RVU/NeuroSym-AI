"""Exceptions for the ImpactForecaster agent.

Kept in a separate module with no optional dependencies so that
``ImpactForecastUnavailable`` can be imported from the top-level
``neurosym`` package even when the ``[forecaster]`` extra is not installed.
"""

from __future__ import annotations


class ImpactForecastUnavailable(RuntimeError):
    """Raised when the LLM fails to return valid hypotheses after retries.

    Never return [] on failure — that is indistinguishable from 'no impact found'.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"ImpactForecaster unavailable: {reason}")
        self.reason = reason
