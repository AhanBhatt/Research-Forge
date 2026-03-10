"""Node: run executable experiment plans in the Python sandbox."""

from __future__ import annotations

import json
import re

from agent.state import ensure_state
from agent.nodes.common import NodeServices
from schemas.result import ExperimentResult


def run(raw_state: dict, services: NodeServices) -> dict:
    state = ensure_state(raw_state)
    results: list[ExperimentResult] = []

    for plan in state.experiment_plans:
        if not state.request.constraints.experiments_enabled:
            results.append(
                ExperimentResult(
                    experiment_id=plan.experiment_id,
                    hypothesis_id=plan.hypothesis_id,
                    status="skipped",
                    hypothesis_outcome="not_tested",
                    likely_next_step="Enable experiments or run externally.",
                )
            )
            continue

        if plan.theoretical_only or not plan.executable_locally or not plan.python_snippet:
            results.append(
                ExperimentResult(
                    experiment_id=plan.experiment_id,
                    hypothesis_id=plan.hypothesis_id,
                    status="skipped",
                    hypothesis_outcome="not_tested",
                    likely_next_step="Run with real data pipeline outside lightweight sandbox.",
                )
            )
            continue

        run_result = services.python_runner.run(plan.python_snippet)
        parsed = _parse_payload(run_result.stdout)

        if run_result.ok:
            results.append(
                ExperimentResult(
                    experiment_id=plan.experiment_id,
                    hypothesis_id=plan.hypothesis_id,
                    status="executed",
                    hypothesis_outcome="inconclusive",
                    metric_deltas=parsed.get("metric_deltas", {}),
                    stdout=run_result.stdout,
                    stderr=run_result.stderr,
                    evidence_quality=0.55,
                    reproducibility_confidence=0.6,
                    confounders=parsed.get("confounders", []),
                    likely_next_step="Replicate on a non-synthetic dataset.",
                )
            )
        else:
            results.append(
                ExperimentResult(
                    experiment_id=plan.experiment_id,
                    hypothesis_id=plan.hypothesis_id,
                    status="failed",
                    hypothesis_outcome="not_tested",
                    stdout=run_result.stdout,
                    stderr=run_result.stderr,
                    error=run_result.blocked_reason or "Execution failed.",
                    evidence_quality=0.0,
                    reproducibility_confidence=0.0,
                    likely_next_step="Fix sandbox-safe script or switch to theoretical analysis.",
                )
            )

    if services.neo4j.enabled:
        for result in results:
            services.neo4j.upsert_result(
                {
                    "result_id": f"{state.run_id}_{result.experiment_id}",
                    "experiment_id": result.experiment_id,
                    "status": result.status,
                    "hypothesis_outcome": result.hypothesis_outcome,
                    "metric_deltas_json": json.dumps(result.metric_deltas),
                    "evidence_quality": result.evidence_quality,
                    "reproducibility_confidence": result.reproducibility_confidence,
                    "error": result.error,
                    "confounders": result.confounders,
                }
            )

    attempted = sum(1 for plan in state.experiment_plans)
    executed = sum(1 for r in results if r.status == "executed")
    logs = state.logs + [f"Experiment execution complete: attempted={attempted}, executed={executed}."]
    return {"experiment_results": [result.model_dump(mode="json") for result in results], "logs": logs}


def _parse_payload(stdout: str) -> dict:
    match = re.search(r"RESULT_JSON:(\{.*\})", stdout, flags=re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}
