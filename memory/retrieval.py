"""Neo4j-backed retrieval helpers used during generation."""

from __future__ import annotations

from memory.graph_queries import HYPOTHESIS_OUTCOMES_QUERY, RELATED_CONCEPTS_QUERY
from tools.neo4j_store import Neo4jStore


class MemoryRetrieval:
    """Convenience retrieval adapter over graph memory."""

    def __init__(self, store: Neo4jStore) -> None:
        self.store = store

    def related_concepts(self, topic: str, limit: int = 10) -> list[str]:
        if not self.store.enabled:
            return []
        if not self.store.has_schema(labels=["Paper", "Topic", "Concept"], rel_types=["ABOUT_TOPIC", "DISCUSSES"]):
            return []
        rows = self.store.run_query(RELATED_CONCEPTS_QUERY, {"topic": topic, "limit": limit})
        return [row["concept"] for row in rows if row.get("concept")]

    def previous_hypothesis_outcomes(self, topic: str, limit: int = 10) -> list[dict[str, str]]:
        if not self.store.enabled:
            return []
        if not self.store.has_schema(
            labels=["Hypothesis", "Topic", "Experiment", "Result"],
            rel_types=["ABOUT_TOPIC", "TESTS", "PRODUCED"],
        ):
            return []
        rows = self.store.run_query(HYPOTHESIS_OUTCOMES_QUERY, {"topic": topic, "limit": limit})
        output: list[dict[str, str]] = []
        for row in rows:
            output.append(
                {
                    "hypothesis_id": row.get("hypothesis_id", ""),
                    "statement": row.get("statement", ""),
                    "outcome": row.get("outcome", "unknown") or "unknown",
                }
            )
        return output
