"""Schemas for experiment planning and execution."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExperimentPlan(BaseModel):
    """Plan for evaluating a research hypothesis."""

    experiment_id: str
    hypothesis_id: str
    title: str
    baseline: str
    variant: str
    data_requirement: str
    metrics: list[str] = Field(default_factory=list)
    success_condition: str
    estimated_complexity: str
    executable_locally: bool = False
    theoretical_only: bool = False
    python_snippet: str | None = None
    estimated_minutes: int = 10


class ExperimentLog(BaseModel):
    """Execution log summary for one experiment."""

    experiment_id: str
    attempted: bool
    executed: bool
    message: str
