"""Node: persist strategy updates for future runs."""

from __future__ import annotations

from agent.state import ensure_state
from agent.nodes.common import NodeServices


def run(raw_state: dict, services: NodeServices) -> dict:
    state = ensure_state(raw_state)
    services.strategy_memory.persist_updates(state.request.topic, state.strategy_updates)
    logs = state.logs + [f"Persisted {len(state.strategy_updates)} strategy updates."]
    return {"logs": logs}
