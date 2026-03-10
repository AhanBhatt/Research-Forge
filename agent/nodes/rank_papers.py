"""Node: rank candidate papers by relevance and recency."""

from __future__ import annotations

from agent.state import ensure_state
from agent.nodes.common import NodeServices


def run(raw_state: dict, services: NodeServices) -> dict:
    state = ensure_state(raw_state)
    max_papers = state.request.constraints.max_papers
    ranked = services.ranker.rank(state.papers, topic=state.request.topic, top_k=max_papers)
    logs = state.logs + [f"Ranked papers and kept top {len(ranked)}."]
    return {"ranked_papers": [paper.model_dump(mode="json") for paper in ranked], "logs": logs}
