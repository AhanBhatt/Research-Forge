"""LangGraph orchestration for Research Forge."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime

from langgraph.graph import END, StateGraph

from agent import state as state_module
from agent.nodes import (
    evaluate_results,
    extract_research_objects,
    generate_final_report,
    generate_hypotheses,
    ingest_topic,
    plan_experiment,
    prioritize_hypotheses,
    query_papers,
    rank_papers,
    reflect,
    run_experiment,
    update_graph_memory,
    update_strategy,
)
from agent.nodes.common import NodeServices
from config import Settings, get_settings
from memory import MemoryRetrieval, StrategyMemory
from schemas.run_report import ResearchRequest, RunReport, RunSummary
from tools import ArxivClient, LLMClient, Neo4jStore, PaperRanker, PythonSandboxRunner, ReportWriter

LOGGER = logging.getLogger(__name__)


def _node_wrapper(fn: Callable[[dict, NodeServices], dict], services: NodeServices) -> Callable[[dict], dict]:
    def wrapped(state: dict) -> dict:
        try:
            return fn(state, services)
        except Exception as exc:  # pragma: no cover - defensive safety
            parsed = state_module.ensure_state(state)
            return {
                "errors": parsed.errors + [f"{fn.__module__}.{fn.__name__}: {exc}"],
                "logs": parsed.logs + [f"Node failure captured at {fn.__name__}: {exc}"],
            }

    return wrapped


def build_graph(services: NodeServices):
    """Construct the stateful LangGraph workflow."""

    graph = StateGraph(state_module.GraphState)
    graph.add_node("ingest_topic", _node_wrapper(ingest_topic.run, services))
    graph.add_node("query_papers", _node_wrapper(query_papers.run, services))
    graph.add_node("rank_papers", _node_wrapper(rank_papers.run, services))
    graph.add_node("extract_research_objects", _node_wrapper(extract_research_objects.run, services))
    graph.add_node("update_graph_memory", _node_wrapper(update_graph_memory.run, services))
    graph.add_node("generate_hypotheses", _node_wrapper(generate_hypotheses.run, services))
    graph.add_node("prioritize_hypotheses", _node_wrapper(prioritize_hypotheses.run, services))
    graph.add_node("plan_experiment", _node_wrapper(plan_experiment.run, services))
    graph.add_node("run_experiment", _node_wrapper(run_experiment.run, services))
    graph.add_node("evaluate_results", _node_wrapper(evaluate_results.run, services))
    graph.add_node("reflect", _node_wrapper(reflect.run, services))
    graph.add_node("update_strategy", _node_wrapper(update_strategy.run, services))
    graph.add_node("generate_final_report", _node_wrapper(generate_final_report.run, services))

    graph.set_entry_point("ingest_topic")
    graph.add_edge("ingest_topic", "query_papers")
    graph.add_edge("query_papers", "rank_papers")
    graph.add_edge("rank_papers", "extract_research_objects")
    graph.add_edge("extract_research_objects", "update_graph_memory")
    graph.add_edge("update_graph_memory", "generate_hypotheses")
    graph.add_edge("generate_hypotheses", "prioritize_hypotheses")
    graph.add_edge("prioritize_hypotheses", "plan_experiment")
    graph.add_edge("plan_experiment", "run_experiment")
    graph.add_edge("run_experiment", "evaluate_results")
    graph.add_edge("evaluate_results", "reflect")
    graph.add_edge("reflect", "update_strategy")
    graph.add_edge("update_strategy", "generate_final_report")
    graph.add_edge("generate_final_report", END)

    return graph.compile()


class ResearchForgeAgent:
    """Facade for running the full research workflow."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        neo4j_store = Neo4jStore(self.settings)
        self.services = NodeServices(
            settings=self.settings,
            arxiv=ArxivClient(
                self.settings.arxiv_api_url,
                timeout_seconds=self.settings.arxiv_timeout_seconds,
                max_retries=self.settings.arxiv_max_retries,
                backoff_seconds=self.settings.arxiv_backoff_seconds,
                max_results_per_query=self.settings.arxiv_max_results_per_query,
            ),
            ranker=PaperRanker(),
            llm=LLMClient(self.settings),
            neo4j=neo4j_store,
            strategy_memory=StrategyMemory(
                neo4j_store=neo4j_store,
                local_cache_path=self.settings.local_strategy_cache_path,
            ),
            memory_retrieval=MemoryRetrieval(neo4j_store),
            python_runner=PythonSandboxRunner(timeout_seconds=self.settings.experiment_timeout_seconds),
            report_writer=ReportWriter(self.settings.artifacts_dir),
        )
        self._graph = build_graph(self.services)

    def run(self, request: ResearchRequest) -> RunReport:
        """Execute one complete cycle and return a typed report."""

        initial_state = state_module.new_state(request)
        final_state = self._graph.invoke(initial_state.model_dump(mode="json"))
        parsed_state = state_module.ensure_state(final_state)
        if parsed_state.final_report is None:
            LOGGER.warning("Workflow finished without final_report; building fallback artifact.")
            summary = RunSummary(
                started_at=parsed_state.started_at,
                completed_at=datetime.utcnow(),
                papers_retrieved=len(parsed_state.papers),
                papers_ranked=len(parsed_state.ranked_papers),
                hypotheses_generated=len(parsed_state.hypotheses),
                experiments_attempted=len(parsed_state.experiment_plans),
                experiments_executed=sum(1 for r in parsed_state.experiment_results if r.status == "executed"),
            )
            fallback = RunReport(
                run_id=parsed_state.run_id,
                topic=parsed_state.request.topic,
                constraints=parsed_state.request.constraints,
                summary=summary,
                retrieved_papers=parsed_state.ranked_papers,
                hypotheses=parsed_state.hypotheses,
                experiment_plans=parsed_state.experiment_plans,
                experiment_results=parsed_state.experiment_results,
                strategy_updates=parsed_state.strategy_updates,
                reflection_notes=parsed_state.reflection_notes
                + [f"Fallback report generated because final node failed. Errors: {parsed_state.errors}"],
                next_research_ideas=parsed_state.next_research_ideas,
            )
            md_path, json_path = self.services.report_writer.write(fallback)
            return fallback.model_copy(update={"report_markdown_path": md_path, "report_json_path": json_path})
        return RunReport.model_validate(parsed_state.final_report)

    def close(self) -> None:
        """Close external resources."""

        self.services.neo4j.close()
