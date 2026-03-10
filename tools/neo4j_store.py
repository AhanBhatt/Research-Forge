"""Neo4j storage layer for long-term research memory."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from config import Settings

LOGGER = logging.getLogger(__name__)


class Neo4jStore:
    """Optional Neo4j-backed memory store."""

    def __init__(self, settings: Settings) -> None:
        self._enabled = settings.neo4j_enabled
        self._database = settings.neo4j_database
        self._driver = None

        if not self._enabled:
            return

        try:
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
            # Force an early connection check so misconfigured Neo4j becomes non-fatal.
            self._driver.verify_connectivity()
        except Exception as exc:  # pragma: no cover - connection edge cases
            LOGGER.warning("Neo4j initialization failed. Memory writes are disabled: %s", exc)
            self._enabled = False
            self._driver = None

    @property
    def enabled(self) -> bool:
        return self._enabled and self._driver is not None

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()

    def run_query(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute a Cypher query and return records as dictionaries."""

        if not self.enabled:
            return []
        parameters = parameters or {}
        try:
            with self._driver.session(database=self._database) as session:
                result = session.run(query, parameters)
                return [dict(record.data()) for record in result]
        except Exception as exc:  # pragma: no cover - runtime db failures
            LOGGER.warning("Neo4j query failed; continuing without graph write: %s", exc)
            return []

    def bulk_write(self, statements: Iterable[tuple[str, dict[str, Any]]]) -> None:
        if not self.enabled:
            return
        try:
            with self._driver.session(database=self._database) as session:
                for query, params in statements:
                    session.run(query, params)
        except Exception as exc:  # pragma: no cover - runtime db failures
            LOGGER.warning("Neo4j bulk write failed; continuing: %s", exc)

    def upsert_topic(self, topic: str) -> None:
        self.run_query(
            """
            MERGE (t:Topic {name: $topic})
            ON CREATE SET t.created_at = datetime()
            SET t.last_seen_at = datetime()
            """,
            {"topic": topic},
        )

    def upsert_paper(self, topic: str, paper: dict[str, Any]) -> None:
        self.run_query(
            """
            MERGE (p:Paper {arxiv_id: $arxiv_id})
            SET p.title = $title,
                p.abstract = $abstract,
                p.published = $published,
                p.updated = $updated,
                p.pdf_url = $pdf_url,
                p.rank_score = $rank_score,
                p.last_ingested_at = datetime()
            WITH p
            MERGE (t:Topic {name: $topic})
            MERGE (p)-[:ABOUT_TOPIC]->(t)
            """,
            {
                "topic": topic,
                "arxiv_id": paper.get("arxiv_id"),
                "title": paper.get("title"),
                "abstract": paper.get("abstract"),
                "published": paper.get("published"),
                "updated": paper.get("updated"),
                "pdf_url": paper.get("pdf_url"),
                "rank_score": paper.get("rank_score", 0.0),
            },
        )

        authors = paper.get("authors", [])
        categories = paper.get("categories", [])
        statements = []
        for author in authors:
            statements.append(
                (
                    """
                    MERGE (a:Author {name: $author})
                    WITH a
                    MATCH (p:Paper {arxiv_id: $arxiv_id})
                    MERGE (p)-[:AUTHORED_BY]->(a)
                    """,
                    {"author": author, "arxiv_id": paper.get("arxiv_id")},
                )
            )
        for category in categories:
            statements.append(
                (
                    """
                    MERGE (c:Concept {name: $category, type: 'category'})
                    WITH c
                    MATCH (p:Paper {arxiv_id: $arxiv_id})
                    MERGE (p)-[:DISCUSSES]->(c)
                    """,
                    {"category": category, "arxiv_id": paper.get("arxiv_id")},
                )
            )
        self.bulk_write(statements)

    def upsert_extraction(self, paper_id: str, extraction: dict[str, Any]) -> None:
        self.run_query(
            """
            MATCH (p:Paper {arxiv_id: $paper_id})
            SET p.research_problem = $research_problem,
                p.method_summary = $method_summary,
                p.extraction_confidence = $confidence
            WITH p
            MERGE (m:Method {name: $method_summary})
            MERGE (p)-[:USES_METHOD]->(m)
            """,
            {
                "paper_id": paper_id,
                "research_problem": extraction.get("research_problem"),
                "method_summary": extraction.get("method_summary"),
                "confidence": extraction.get("confidence_score", 0.5),
            },
        )
        self._link_string_list(
            paper_id,
            extraction.get("datasets", []),
            node_label="Dataset",
            rel_type="EVALUATED_ON",
        )
        self._link_string_list(
            paper_id,
            extraction.get("metrics", []),
            node_label="Metric",
            rel_type="MEASURES_WITH",
        )
        self._link_string_list(
            paper_id,
            extraction.get("assumptions", []),
            node_label="Assumption",
            rel_type="ASSUMES",
        )
        self._link_string_list(
            paper_id,
            extraction.get("limitations", []),
            node_label="Limitation",
            rel_type="HAS_LIMITATION",
        )
        self._link_string_list(
            paper_id,
            extraction.get("main_claims", []),
            node_label="Claim",
            rel_type="CLAIMS",
        )

    def upsert_hypothesis(self, topic: str, hypothesis: dict[str, Any]) -> None:
        self.run_query(
            """
            MERGE (h:Hypothesis {hypothesis_id: $hypothesis_id})
            SET h.statement = $statement,
                h.rationale = $rationale,
                h.novelty = $novelty,
                h.feasibility = $feasibility,
                h.information_gain = $information_gain,
                h.compute_cost = $compute_cost,
                h.priority_score = $priority_score
            WITH h
            MERGE (t:Topic {name: $topic})
            MERGE (h)-[:ABOUT_TOPIC]->(t)
            """,
            {"topic": topic, **hypothesis},
        )
        for paper_id in hypothesis.get("grounding_papers", []):
            self.run_query(
                """
                MATCH (h:Hypothesis {hypothesis_id: $hypothesis_id})
                MATCH (p:Paper {arxiv_id: $paper_id})
                MERGE (h)-[:INSPIRED_BY]->(p)
                """,
                {"hypothesis_id": hypothesis.get("hypothesis_id"), "paper_id": paper_id},
            )

    def upsert_experiment(self, plan: dict[str, Any]) -> None:
        self.run_query(
            """
            MERGE (e:Experiment {experiment_id: $experiment_id})
            SET e.title = $title,
                e.baseline = $baseline,
                e.variant = $variant,
                e.data_requirement = $data_requirement,
                e.success_condition = $success_condition,
                e.estimated_complexity = $estimated_complexity,
                e.executable_locally = $executable_locally,
                e.theoretical_only = $theoretical_only,
                e.estimated_minutes = $estimated_minutes
            WITH e
            MATCH (h:Hypothesis {hypothesis_id: $hypothesis_id})
            MERGE (e)-[:TESTS]->(h)
            """,
            plan,
        )

    def upsert_result(self, result: dict[str, Any]) -> None:
        self.run_query(
            """
            MERGE (r:Result {result_id: $result_id})
            SET r.status = $status,
                r.hypothesis_outcome = $hypothesis_outcome,
                r.metric_deltas_json = $metric_deltas_json,
                r.evidence_quality = $evidence_quality,
                r.reproducibility_confidence = $reproducibility_confidence,
                r.error = $error
            WITH r
            MATCH (e:Experiment {experiment_id: $experiment_id})
            MERGE (e)-[:PRODUCED]->(r)
            """,
            result,
        )
        for confounder in result.get("confounders", []):
            self.run_query(
                """
                MERGE (f:FailureMode {name: $confounder})
                WITH f
                MATCH (r:Result {result_id: $result_id})
                MERGE (r)-[:REVEALS]->(f)
                """,
                {"confounder": confounder, "result_id": result.get("result_id")},
            )

    def upsert_strategy_update(self, topic: str, update: dict[str, Any]) -> None:
        self.run_query(
            """
            MERGE (s:StrategyUpdate {update_id: $update_id})
            SET s.timestamp = datetime($timestamp),
                s.category = $category,
                s.predicted = $predicted,
                s.observed = $observed,
                s.failure_or_success_reason = $failure_or_success_reason,
                s.recommendation = $recommendation,
                s.confidence_delta = $confidence_delta,
                s.impact_score = $impact_score
            WITH s
            MERGE (t:Topic {name: $topic})
            MERGE (s)-[:ABOUT_TOPIC]->(t)
            """,
            {"topic": topic, **update},
        )
        for result_id in update.get("based_on_result_ids", []):
            self.run_query(
                """
                MATCH (s:StrategyUpdate {update_id: $update_id})
                MATCH (r:Result {result_id: $result_id})
                MERGE (s)-[:BASED_ON]->(r)
                """,
                {"update_id": update.get("update_id"), "result_id": result_id},
            )

    def fetch_strategy_hints(self, topic: str, limit: int = 8) -> list[str]:
        rows = self.run_query(
            """
            MATCH (s:StrategyUpdate)-[:ABOUT_TOPIC]->(t:Topic {name: $topic})
            RETURN s.recommendation AS recommendation
            ORDER BY s.timestamp DESC
            LIMIT $limit
            """,
            {"topic": topic, "limit": limit},
        )
        return [row["recommendation"] for row in rows if row.get("recommendation")]

    def upsert_research_idea(self, topic: str, idea_id: str, text: str, source_result_ids: list[str] | None = None) -> None:
        source_result_ids = source_result_ids or []
        self.run_query(
            """
            MERGE (ri:ResearchIdea {idea_id: $idea_id})
            SET ri.text = $text,
                ri.updated_at = datetime()
            WITH ri
            MERGE (t:Topic {name: $topic})
            MERGE (ri)-[:ABOUT_TOPIC]->(t)
            """,
            {"idea_id": idea_id, "text": text, "topic": topic},
        )
        for result_id in source_result_ids:
            self.run_query(
                """
                MATCH (ri:ResearchIdea {idea_id: $idea_id})
                MATCH (r:Result {result_id: $result_id})
                MERGE (ri)-[:DERIVED_FROM]->(r)
                """,
                {"idea_id": idea_id, "result_id": result_id},
            )

    def _link_string_list(self, paper_id: str, values: list[str], node_label: str, rel_type: str) -> None:
        if not values:
            return
        for value in values:
            self.run_query(
                f"""
                MERGE (x:{node_label} {{name: $value}})
                WITH x
                MATCH (p:Paper {{arxiv_id: $paper_id}})
                MERGE (p)-[:{rel_type}]->(x)
                """,
                {"paper_id": paper_id, "value": value},
            )
