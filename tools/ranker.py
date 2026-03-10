"""Ranking utilities for candidate papers and hypotheses."""

from __future__ import annotations

from datetime import datetime, timezone
from math import exp

from schemas.paper import Paper


class PaperRanker:
    """Ranking logic combining lexical relevance and recency."""

    def __init__(self, relevance_weight: float = 0.7, recency_weight: float = 0.3) -> None:
        self.relevance_weight = relevance_weight
        self.recency_weight = recency_weight

    def rank(self, papers: list[Paper], topic: str, top_k: int | None = None) -> list[Paper]:
        topic_tokens = self._tokenize(topic)
        ranked: list[Paper] = []
        for paper in papers:
            relevance = self._lexical_relevance(topic_tokens, self._tokenize(f"{paper.title} {paper.abstract}"))
            recency = self._recency_score(paper.updated or paper.published)
            score = (self.relevance_weight * relevance) + (self.recency_weight * recency)
            ranked.append(
                paper.model_copy(
                    update={
                        "relevance_score": round(relevance, 4),
                        "recency_score": round(recency, 4),
                        "rank_score": round(score, 4),
                    }
                )
            )
        ranked.sort(key=lambda p: p.rank_score, reverse=True)
        if top_k is not None:
            ranked = ranked[:top_k]
        return ranked

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {token.lower() for token in text.split() if len(token.strip()) > 2}

    @staticmethod
    def _lexical_relevance(topic_tokens: set[str], doc_tokens: set[str]) -> float:
        if not topic_tokens:
            return 0.0
        overlap = len(topic_tokens.intersection(doc_tokens))
        return overlap / max(1, len(topic_tokens))

    @staticmethod
    def _recency_score(timestamp: datetime | None) -> float:
        if timestamp is None:
            return 0.0
        now = datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        days_old = max((now - timestamp).days, 0)
        # Smooth decay where newer papers score higher.
        return float(exp(-days_old / 365.0))
