"""Research Forge package."""

from __future__ import annotations

__all__ = ["ResearchForgeAgent"]


def __getattr__(name: str):
    if name == "ResearchForgeAgent":
        from agent.graph import ResearchForgeAgent

        return ResearchForgeAgent
    raise AttributeError(name)
