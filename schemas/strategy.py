"""Schemas for reflection and strategy updates."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, confloat


class StrategyUpdate(BaseModel):
    """A persistent learning signal generated after each run."""

    update_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    category: Literal["query", "extraction", "hypothesis", "experiment", "evaluation"]
    predicted: str
    observed: str
    failure_or_success_reason: str
    recommendation: str
    confidence_delta: confloat(ge=-1.0, le=1.0) = 0.0
    impact_score: confloat(ge=0.0, le=1.0) = 0.5
    based_on_result_ids: list[str] = Field(default_factory=list)


class StrategyMemorySnapshot(BaseModel):
    """Aggregated strategy memory for a topic."""

    topic: str
    hints: list[str] = Field(default_factory=list)
    updates: list[StrategyUpdate] = Field(default_factory=list)
