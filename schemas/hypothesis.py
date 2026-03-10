"""Schemas for generated research hypotheses."""

from __future__ import annotations

from pydantic import BaseModel, Field, confloat


Score = confloat(ge=0.0, le=1.0)


class Hypothesis(BaseModel):
    """A testable, grounded research hypothesis."""

    hypothesis_id: str
    statement: str
    rationale: str
    grounding_papers: list[str] = Field(default_factory=list)
    novelty: Score = 0.5
    feasibility: Score = 0.5
    information_gain: Score = 0.5
    compute_cost: Score = 0.5
    expected_direction: str = "unknown"
    priority_score: Score = 0.5


class HypothesisBatch(BaseModel):
    """Batch container for LLM structured outputs."""

    hypotheses: list[Hypothesis] = Field(default_factory=list)
