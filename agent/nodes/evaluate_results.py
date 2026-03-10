"""Node: evaluate experiment outcomes against hypotheses."""

from __future__ import annotations

from agent.state import ensure_state
from agent.nodes.common import NodeServices
from schemas.result import ExperimentResult


def run(raw_state: dict, services: NodeServices) -> dict:
    state = ensure_state(raw_state)
    evaluated: list[ExperimentResult] = []
    notes = list(state.reflection_notes)

    for result in state.experiment_results:
        if result.status != "executed":
            evaluated.append(result)
            continue

        primary = result.metric_deltas.get("primary_score", 0.0)
        runtime = result.metric_deltas.get("runtime_cost", 0.0)

        if primary >= 0.03 and runtime <= 0.10:
            outcome = "supported"
            evidence = min(0.8, 0.55 + primary)
            next_step = "Scale the variant to larger and real datasets."
        elif primary < 0:
            outcome = "unsupported"
            evidence = 0.65
            next_step = "Inspect whether the intervention conflicts with baseline assumptions."
        else:
            outcome = "inconclusive"
            evidence = 0.5
            next_step = "Run more seeds and dataset slices to reduce uncertainty."

        evaluated_result = result.model_copy(
            update={
                "hypothesis_outcome": outcome,
                "evidence_quality": round(max(0.0, min(1.0, evidence)), 3),
                "reproducibility_confidence": round(max(0.0, min(1.0, result.reproducibility_confidence)), 3),
                "likely_next_step": next_step,
            }
        )
        evaluated.append(evaluated_result)
        notes.append(
            f"{result.experiment_id}: predicted local signal, observed primary_score={primary:+.4f}, outcome={outcome}."
        )

    logs = state.logs + [f"Evaluated {len(evaluated)} experiment results."]
    return {
        "experiment_results": [result.model_dump(mode="json") for result in evaluated],
        "reflection_notes": notes,
        "logs": logs,
    }
