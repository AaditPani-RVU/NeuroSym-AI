from typing import Literal

from pydantic import BaseModel, Field


class ImpactForecastUnavailable(RuntimeError):
    """Raised when the LLM fails to return valid hypotheses after retries.

    Never return [] on failure — that is indistinguishable from 'no impact found'.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"ImpactForecaster unavailable: {reason}")
        self.reason = reason


class ImpactHypothesis(BaseModel):
    area: str
    reason: str
    confidence: float


class EvidenceItem(BaseModel):
    rule_id: str
    evidence_type: Literal["path", "regex", "diff_snippet"]
    value: str


class ImpactEdge(BaseModel):
    src: str
    dst: str
    reason: str


class ImpactForecast(BaseModel):
    risk: Literal["LOW", "MEDIUM", "HIGH"]
    impacts: list[ImpactHypothesis] = Field(default_factory=list)
    required_actions: list[str] = Field(default_factory=list)
    triggered_rules: list[str] = Field(default_factory=list)

    # New fields
    owners_to_notify: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    impact_chain: list[ImpactEdge] = Field(default_factory=list)
