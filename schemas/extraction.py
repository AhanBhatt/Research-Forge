"""Schemas for structured extraction from research papers."""

from __future__ import annotations

from pydantic import BaseModel, Field, confloat


class ResearchObjectExtraction(BaseModel):
    """Structured representation of a paper's research content."""

    research_problem: str
    main_claims: list[str] = Field(default_factory=list)
    method_summary: str
    assumptions: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    future_work: list[str] = Field(default_factory=list)
    reproducibility_clues: list[str] = Field(default_factory=list)
    follow_up_hypotheses: list[str] = Field(default_factory=list)
    confidence_score: confloat(ge=0.0, le=1.0) = 0.5


class PaperExtraction(BaseModel):
    """Extraction object tied to a specific paper."""

    paper_id: str
    extraction: ResearchObjectExtraction
