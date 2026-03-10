"""Node: produce explicit reflection over prediction vs outcome."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from agent.state import ensure_state
from agent.nodes.common import NodeServices
from schemas.strategy import StrategyUpdate


def run(raw_state: dict, services: NodeServices) -> dict:
    state = ensure_state(raw_state)
    updates: list[StrategyUpdate] = list(state.strategy_updates)
    notes: list[str] = list(state.reflection_notes)

    papers_found = len(state.ranked_papers)
    target_papers = state.request.constraints.max_papers
    if papers_found < max(4, target_papers // 2):
        updates.append(
            StrategyUpdate(
                update_id=f"su_{uuid4().hex[:10]}",
                timestamp=datetime.utcnow(),
                category="query",
                predicted=f"query_attempts={len(state.query_attempts)} should yield >= {target_papers // 2} papers",
                observed=f"retrieved={papers_found}",
                failure_or_success_reason="Insufficient paper yield for robust hypothesis generation.",
                recommendation="Broaden query by removing strict category filters and add adjacent terminology.",
                confidence_delta=-0.15,
                impact_score=0.72,
                based_on_result_ids=[],
            )
        )
    else:
        updates.append(
            StrategyUpdate(
                update_id=f"su_{uuid4().hex[:10]}",
                timestamp=datetime.utcnow(),
                category="query",
                predicted=f"query style '{state.query_text[:60]}' should retrieve diverse evidence",
                observed=f"retrieved={papers_found}, attempts={len(state.query_attempts)}",
                failure_or_success_reason="Query style produced usable paper set.",
                recommendation="Preserve this query template and append contradiction-focused keywords next cycle.",
                confidence_delta=0.12,
                impact_score=0.62,
                based_on_result_ids=[],
            )
        )

    extraction_conf = (
        sum(ext.confidence_score for ext in state.extractions.values()) / max(1, len(state.extractions))
        if state.extractions
        else 0.0
    )
    updates.append(
        StrategyUpdate(
            update_id=f"su_{uuid4().hex[:10]}",
            timestamp=datetime.utcnow(),
            category="extraction",
            predicted="Current extraction prompt should yield confidence >= 0.6",
            observed=f"average_confidence={extraction_conf:.2f}",
            failure_or_success_reason=(
                "Prompt produced high confidence structured objects." if extraction_conf >= 0.6 else "Low-confidence extraction; abstracts alone were limiting."
            ),
            recommendation=(
                "Keep extraction prompt mostly unchanged."
                if extraction_conf >= 0.6
                else "Add explicit schema examples and request uncertainty notes for each field."
            ),
            confidence_delta=0.08 if extraction_conf >= 0.6 else -0.12,
            impact_score=0.66,
            based_on_result_ids=[],
        )
    )

    result_by_hypothesis = {result.hypothesis_id: result for result in state.experiment_results}
    for prediction in state.predictions:
        result = result_by_hypothesis.get(prediction.hypothesis_id)
        if result is None:
            continue
        predicted_positive = prediction.expected_support_probability >= 0.6
        observed_positive = result.hypothesis_outcome == "supported"
        aligned = predicted_positive == observed_positive
        updates.append(
            StrategyUpdate(
                update_id=f"su_{uuid4().hex[:10]}",
                timestamp=datetime.utcnow(),
                category="hypothesis",
                predicted=(
                    f"{prediction.hypothesis_id} support_probability={prediction.expected_support_probability:.2f}"
                ),
                observed=f"outcome={result.hypothesis_outcome}",
                failure_or_success_reason=(
                    "Prediction aligned with observed outcome." if aligned else "Prediction missed observed outcome."
                ),
                recommendation=(
                    "Increase confidence in this hypothesis scoring pattern."
                    if aligned
                    else "Reduce confidence in high-feasibility priors; weight empirical variance more heavily."
                ),
                confidence_delta=0.10 if aligned else -0.16,
                impact_score=0.58,
                based_on_result_ids=[f"{state.run_id}_{result.experiment_id}"],
            )
        )

    skipped = [r for r in state.experiment_results if r.status == "skipped"]
    if skipped:
        updates.append(
            StrategyUpdate(
                update_id=f"su_{uuid4().hex[:10]}",
                timestamp=datetime.utcnow(),
                category="experiment",
                predicted="At least one executable local experiment should run.",
                observed=f"skipped={len(skipped)} of {len(state.experiment_results)}",
                failure_or_success_reason="Experiment plans were theoretical or disabled.",
                recommendation="Prioritize low-cost synthetic or tabular experiment templates for faster feedback loops.",
                confidence_delta=-0.1,
                impact_score=0.7,
                based_on_result_ids=[f"{state.run_id}_{r.experiment_id}" for r in skipped],
            )
        )

    notes.append(
        f"Reflection complete: {len(updates)} strategy updates generated from predictions, outcomes, and pipeline telemetry."
    )
    logs = state.logs + [f"Generated {len(updates)} reflection-driven strategy updates."]
    return {
        "strategy_updates": [update.model_dump(mode="json") for update in updates],
        "reflection_notes": notes,
        "logs": logs,
    }
