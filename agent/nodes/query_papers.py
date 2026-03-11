"""Node: retrieve papers from arXiv."""

from __future__ import annotations

from agent.state import ensure_state
from agent.nodes.common import NodeServices


def run(raw_state: dict, services: NodeServices) -> dict:
    state = ensure_state(raw_state)
    constraints = state.request.constraints
    topic_query = state.query_text or state.request.topic

    papers, attempts = services.arxiv.search(
        topic=topic_query,
        max_results=min(max(constraints.max_papers + 4, constraints.max_papers), 20),
        preferred_categories=constraints.preferred_categories,
        date_from=constraints.date_from,
        date_to=constraints.date_to,
    )

    logs = state.logs + [f"Queried arXiv with {len(attempts)} attempts, retrieved {len(papers)} papers."]
    errors = list(state.errors)
    if not papers:
        errors.append("Paper discovery returned no results.")

    return {
        "papers": [paper.model_dump(mode="json") for paper in papers],
        "query_attempts": state.query_attempts + attempts,
        "logs": logs,
        "errors": errors,
    }
