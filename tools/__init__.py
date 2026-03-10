"""Tool layer exports."""

from __future__ import annotations

__all__ = [
    "ArxivClient",
    "LLMClient",
    "Neo4jStore",
    "PaperRanker",
    "PythonRunResult",
    "PythonSandboxRunner",
    "ReportWriter",
]


def __getattr__(name: str):
    if name == "ArxivClient":
        from tools.arxiv_client import ArxivClient

        return ArxivClient
    if name == "LLMClient":
        from tools.llm_client import LLMClient

        return LLMClient
    if name == "Neo4jStore":
        from tools.neo4j_store import Neo4jStore

        return Neo4jStore
    if name == "PaperRanker":
        from tools.ranker import PaperRanker

        return PaperRanker
    if name == "PythonRunResult":
        from tools.python_runner import PythonRunResult

        return PythonRunResult
    if name == "PythonSandboxRunner":
        from tools.python_runner import PythonSandboxRunner

        return PythonSandboxRunner
    if name == "ReportWriter":
        from tools.report_writer import ReportWriter

        return ReportWriter
    raise AttributeError(name)
