"""Node: assemble and persist final run artifacts."""

from __future__ import annotations

from datetime import datetime

from agent.state import ensure_state
from agent.nodes.common import NodeServices
from schemas.run_report import RunReport, RunSummary


def run(raw_state: dict, services: NodeServices) -> dict:
    state = ensure_state(raw_state)
    next_ideas = _build_next_ideas(state)
    result_ids = [f"{state.run_id}_{r.experiment_id}" for r in state.experiment_results if r.status == "executed"]

    summary = RunSummary(
        started_at=state.started_at,
        completed_at=datetime.utcnow(),
        papers_retrieved=len(state.papers),
        papers_ranked=len(state.ranked_papers),
        hypotheses_generated=len(state.hypotheses),
        experiments_attempted=len(state.experiment_plans),
        experiments_executed=sum(1 for r in state.experiment_results if r.status == "executed"),
    )
    report = RunReport(
        run_id=state.run_id,
        topic=state.request.topic,
        constraints=state.request.constraints,
        summary=summary,
        retrieved_papers=state.ranked_papers,
        hypotheses=state.hypotheses,
        experiment_plans=state.experiment_plans,
        experiment_results=state.experiment_results,
        strategy_updates=state.strategy_updates,
        reflection_notes=state.reflection_notes,
        next_research_ideas=next_ideas,
    )
    md_path, json_path = services.report_writer.write(report)
    report = report.model_copy(update={"report_markdown_path": md_path, "report_json_path": json_path})

    logs = list(state.logs)
    if services.neo4j.enabled:
        try:
            for idx, idea in enumerate(next_ideas, start=1):
                services.neo4j.upsert_research_idea(
                    topic=state.request.topic,
                    idea_id=f"{state.run_id}_idea_{idx}",
                    text=idea,
                    source_result_ids=result_ids,
                )
        except Exception as exc:  # pragma: no cover - defensive fallback
            logs.append(f"Optional Neo4j research idea write failed: {exc}")

    logs.append(f"Wrote final report artifacts to {md_path} and {json_path}.")
    return {
        "final_report": report.model_dump(mode="json"),
        "next_research_ideas": next_ideas,
        "logs": logs,
    }


def _build_next_ideas(state) -> list[str]:
    ideas: list[str] = []
    for hyp in state.prioritized_hypotheses[:3]:
        ideas.append(f"Scale and stress-test hypothesis `{hyp.hypothesis_id}` across broader dataset slices.")
    for result in state.experiment_results:
        if result.hypothesis_outcome == "unsupported":
            ideas.append(
                f"Investigate failure mode for `{result.hypothesis_id}`: "
                f"control for confounders {', '.join(result.confounders) or 'not yet identified'}."
            )
    for update in state.strategy_updates[:2]:
        ideas.append(f"Apply strategy update: {update.recommendation}")
    return list(dict.fromkeys(ideas))[:8]
