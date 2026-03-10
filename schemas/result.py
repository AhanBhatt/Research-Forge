"""Schemas for experiment outcomes and evidence evaluation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, confloat


EvidenceScore = confloat(ge=0.0, le=1.0)


class ExperimentResult(BaseModel):
    """Structured result of a planned experiment."""

    experiment_id: str
    hypothesis_id: str
    status: Literal["executed", "skipped", "failed"] = "skipped"
    hypothesis_outcome: Literal["supported", "unsupported", "inconclusive", "not_tested"] = "not_tested"
    metric_deltas: dict[str, float] = Field(default_factory=dict)
    stdout: str = ""
    stderr: str = ""
    evidence_quality: EvidenceScore = 0.3
    reproducibility_confidence: EvidenceScore = 0.3
    confounders: list[str] = Field(default_factory=list)
    likely_next_step: str = ""
    error: str | None = None
