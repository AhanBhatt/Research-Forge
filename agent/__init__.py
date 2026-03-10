"""Agent orchestration exports."""

from __future__ import annotations

__all__ = ["ResearchForgeAgent", "build_graph"]


def __getattr__(name: str):
    if name in {"ResearchForgeAgent", "build_graph"}:
        from agent.graph import ResearchForgeAgent, build_graph

        return {"ResearchForgeAgent": ResearchForgeAgent, "build_graph": build_graph}[name]
    raise AttributeError(name)
