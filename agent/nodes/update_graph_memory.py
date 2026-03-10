"""Node: persist discovered papers and extraction objects to graph memory."""

from __future__ import annotations

from agent.state import ensure_state
from agent.nodes.common import NodeServices


def run(raw_state: dict, services: NodeServices) -> dict:
    state = ensure_state(raw_state)
    if not services.neo4j.enabled:
        logs = state.logs + ["Neo4j not configured; skipped graph memory write."]
        return {"logs": logs}

    topic = state.request.topic
    services.neo4j.upsert_topic(topic)
    for paper in state.ranked_papers:
        services.neo4j.upsert_paper(topic, paper.model_dump(mode="json"))
        extraction = state.extractions.get(paper.arxiv_id)
        if extraction:
            services.neo4j.upsert_extraction(paper.arxiv_id, extraction)

    logs = state.logs + [f"Persisted {len(state.ranked_papers)} papers and extractions to Neo4j."]
    return {"logs": logs}
