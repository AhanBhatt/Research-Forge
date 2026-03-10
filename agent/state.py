"""Shared state model for the LangGraph workflow."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, confloat
from typing_extensions import TypedDict

from schemas.experiment import ExperimentPlan
from schemas.extraction import ResearchObjectExtraction
from schemas.hypothesis import Hypothesis
from schemas.paper import Paper
from schemas.result import ExperimentResult
from schemas.run_report import ResearchRequest, RunReport
from schemas.strategy import StrategyMemorySnapshot, StrategyUpdate


class HypothesisPrediction(BaseModel):
    """Predicted success odds for top-ranked hypotheses."""

    hypothesis_id: str
    expected_support_probability: confloat(ge=0.0, le=1.0) = 0.5
    rationale: str


class ResearchState(BaseModel):
    """Complete mutable state passed between graph nodes."""

    run_id: str
    started_at: datetime
    request: ResearchRequest

    query_text: str = ""
    query_attempts: list[str] = Field(default_factory=list)

    papers: list[Paper] = Field(default_factory=list)
    ranked_papers: list[Paper] = Field(default_factory=list)
    extractions: dict[str, ResearchObjectExtraction] = Field(default_factory=dict)

    hypotheses: list[Hypothesis] = Field(default_factory=list)
    prioritized_hypotheses: list[Hypothesis] = Field(default_factory=list)
    predictions: list[HypothesisPrediction] = Field(default_factory=list)

    experiment_plans: list[ExperimentPlan] = Field(default_factory=list)
    experiment_results: list[ExperimentResult] = Field(default_factory=list)

    strategy_snapshot: StrategyMemorySnapshot | None = None
    strategy_updates: list[StrategyUpdate] = Field(default_factory=list)
    reflection_notes: list[str] = Field(default_factory=list)
    next_research_ideas: list[str] = Field(default_factory=list)

    final_report: RunReport | None = None
    logs: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class GraphState(TypedDict, total=False):
    """TypedDict used by LangGraph to define state channels."""

    run_id: str
    started_at: str
    request: dict[str, Any]

    query_text: str
    query_attempts: list[str]

    papers: list[dict[str, Any]]
    ranked_papers: list[dict[str, Any]]
    extractions: dict[str, dict[str, Any]]

    hypotheses: list[dict[str, Any]]
    prioritized_hypotheses: list[dict[str, Any]]
    predictions: list[dict[str, Any]]

    experiment_plans: list[dict[str, Any]]
    experiment_results: list[dict[str, Any]]

    strategy_snapshot: dict[str, Any]
    strategy_updates: list[dict[str, Any]]
    reflection_notes: list[str]
    next_research_ideas: list[str]

    final_report: dict[str, Any]
    logs: list[str]
    errors: list[str]


def new_state(request: ResearchRequest) -> ResearchState:
    """Create the initial state for a run."""

    return ResearchState(
        run_id=f"run_{uuid4().hex[:12]}",
        started_at=datetime.utcnow(),
        request=request,
    )


def ensure_state(raw_state: dict | ResearchState) -> ResearchState:
    """Validate state payload from LangGraph node input."""

    if isinstance(raw_state, ResearchState):
        return raw_state
    return ResearchState.model_validate(raw_state)
