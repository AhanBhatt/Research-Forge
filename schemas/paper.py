"""Schemas for paper metadata."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class Paper(BaseModel):
    """Normalized paper metadata used across the workflow."""

    arxiv_id: str = Field(..., description="Canonical arXiv identifier.")
    title: str
    abstract: str
    authors: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    published: datetime | None = None
    updated: datetime | None = None
    pdf_url: HttpUrl | None = None
    relevance_score: float = 0.0
    recency_score: float = 0.0
    rank_score: float = 0.0
