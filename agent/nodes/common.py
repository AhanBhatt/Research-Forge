"""Common node helpers and dependency container."""

from __future__ import annotations

from dataclasses import dataclass

from config import Settings
from memory import MemoryRetrieval, StrategyMemory
from tools import (
    ArxivClient,
    LLMClient,
    Neo4jStore,
    PaperRanker,
    PythonSandboxRunner,
    ReportWriter,
)


@dataclass
class NodeServices:
    """Dependency bundle injected into each graph node."""

    settings: Settings
    arxiv: ArxivClient
    ranker: PaperRanker
    llm: LLMClient
    neo4j: Neo4jStore
    strategy_memory: StrategyMemory
    memory_retrieval: MemoryRetrieval
    python_runner: PythonSandboxRunner
    report_writer: ReportWriter
