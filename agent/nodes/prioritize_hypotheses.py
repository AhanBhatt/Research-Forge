"""Node: prioritize hypotheses for experimentation."""

from __future__ import annotations

from agent.state import HypothesisPrediction, ensure_state
from agent.nodes.common import NodeServices
from schemas.hypothesis import Hypothesis


def run(raw_state: dict, services: NodeServices) -> dict:
    state = ensure_state(raw_state)
    scored: list[Hypothesis] = []
    for hyp in state.hypotheses:
        priority = (
            (0.30 * hyp.novelty)
            + (0.25 * hyp.feasibility)
            + (0.30 * hyp.information_gain)
            + (0.15 * (1.0 - hyp.compute_cost))
        )
        scored.append(hyp.model_copy(update={"priority_score": round(min(max(priority, 0.0), 1.0), 4)}))

    scored.sort(key=lambda h: h.priority_score, reverse=True)
    budget = state.request.constraints.experiment_budget
    prioritized = scored[: max(1, min(len(scored), budget + 2))]

    predictions: list[HypothesisPrediction] = []
    for hyp in prioritized:
        expected_support = round((hyp.feasibility * 0.6) + ((1.0 - hyp.compute_cost) * 0.4), 3)
        predictions.append(
            HypothesisPrediction(
                hypothesis_id=hyp.hypothesis_id,
                expected_support_probability=expected_support,
                rationale=(
                    f"Estimated from feasibility={hyp.feasibility:.2f} and compute_cost={hyp.compute_cost:.2f}."
                ),
            )
        )

    if services.neo4j.enabled:
        for hyp in scored:
            services.neo4j.upsert_hypothesis(state.request.topic, hyp.model_dump(mode="json"))

    logs = state.logs + [f"Prioritized {len(prioritized)} hypotheses for planning."]
    return {
        "hypotheses": [h.model_dump(mode="json") for h in scored],
        "prioritized_hypotheses": [h.model_dump(mode="json") for h in prioritized],
        "predictions": [p.model_dump(mode="json") for p in predictions],
        "logs": logs,
    }
