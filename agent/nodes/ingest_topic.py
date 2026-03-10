"""Node: ingest topic and initialize run context."""

from __future__ import annotations

from agent.state import ensure_state
from agent.nodes.common import NodeServices


def run(raw_state: dict, services: NodeServices) -> dict:
    state = ensure_state(raw_state)
    topic = state.request.topic.strip()
    snapshot = services.strategy_memory.load_snapshot(topic)
    related = services.memory_retrieval.related_concepts(topic, limit=5)

    # Keep arXiv query text focused on the user topic. Categories are handled separately.
    query_text = topic

    logs = state.logs + [
        f"Ingested topic '{topic}'.",
        f"Loaded {len(snapshot.hints)} prior strategy hints.",
        f"Retrieved {len(related)} related memory concepts.",
    ]
    return {
        "query_text": query_text,
        "strategy_snapshot": snapshot.model_dump(mode="json"),
        "logs": logs,
    }
