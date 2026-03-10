"""Node: create executable or theoretical experiment plans."""

from __future__ import annotations

import json
from textwrap import dedent
from uuid import uuid4

from pydantic import BaseModel, Field

from agent.prompts import EXPERIMENT_PLAN_SYSTEM_PROMPT, experiment_plan_user_prompt
from agent.state import ensure_state
from agent.nodes.common import NodeServices
from schemas.experiment import ExperimentPlan
from schemas.hypothesis import Hypothesis


class ExperimentPlanBatch(BaseModel):
    plans: list[ExperimentPlan] = Field(default_factory=list)


def run(raw_state: dict, services: NodeServices) -> dict:
    state = ensure_state(raw_state)
    constraints = state.request.constraints
    candidates = state.prioritized_hypotheses[: max(1, constraints.experiment_budget)]
    if not candidates:
        logs = state.logs + ["No prioritized hypotheses available; skipped experiment planning."]
        return {"experiment_plans": [], "logs": logs}

    fallback = lambda: ExperimentPlanBatch(plans=_heuristic_plans(candidates, state.request.topic, constraints.experiments_enabled))
    payload = json.dumps([hyp.model_dump(mode="json") for hyp in candidates], indent=2)
    try:
        batch = services.llm.generate_structured(
            system_prompt=EXPERIMENT_PLAN_SYSTEM_PROMPT,
            user_prompt=experiment_plan_user_prompt(state.request.topic, payload, constraints.experiment_budget),
            schema=ExperimentPlanBatch,
            retries=1,
            fallback_factory=fallback,
        )
        plans = _normalize_plan_batch(batch.plans, constraints.experiments_enabled)
    except Exception:
        plans = _heuristic_plans(candidates, state.request.topic, constraints.experiments_enabled)

    if services.neo4j.enabled:
        for plan in plans:
            services.neo4j.upsert_experiment(plan.model_dump(mode="json"))

    logs = state.logs + [f"Planned {len(plans)} experiments ({'enabled' if constraints.experiments_enabled else 'disabled'})."]
    return {"experiment_plans": [plan.model_dump(mode="json") for plan in plans], "logs": logs}


def _normalize_plan_batch(plans: list[ExperimentPlan], experiments_enabled: bool) -> list[ExperimentPlan]:
    output: list[ExperimentPlan] = []
    for plan in plans:
        update = {}
        if not plan.experiment_id:
            update["experiment_id"] = f"exp_{uuid4().hex[:8]}"
        normalized = plan.model_copy(update=update)
        if not experiments_enabled:
            normalized = normalized.model_copy(update={"executable_locally": False, "theoretical_only": True, "python_snippet": None})
        output.append(normalized)
    return output


def _heuristic_plans(hypotheses: list[Hypothesis], topic: str, experiments_enabled: bool) -> list[ExperimentPlan]:
    plans: list[ExperimentPlan] = []
    for idx, hypothesis in enumerate(hypotheses, start=1):
        executable = experiments_enabled and _is_lightweight_topic(topic)
        theoretical_only = not executable
        snippet = _build_default_snippet(hypothesis.statement) if executable else None
        plans.append(
            ExperimentPlan(
                experiment_id=f"exp_{uuid4().hex[:8]}",
                hypothesis_id=hypothesis.hypothesis_id,
                title=f"Baseline-vs-variant test #{idx}",
                baseline="Current best-practice baseline from retrieved papers",
                variant=f"Targeted intervention for hypothesis: {hypothesis.statement}",
                data_requirement="Toy synthetic data for signal check; replace with domain dataset for full validation",
                metrics=["primary_score", "runtime_cost"],
                success_condition="Variant improves primary_score by >= 0.03 without runtime_cost increase > 0.10",
                estimated_complexity="low" if executable else "high",
                executable_locally=executable,
                theoretical_only=theoretical_only,
                python_snippet=snippet,
                estimated_minutes=8 if executable else 45,
            )
        )
    return plans


def _is_lightweight_topic(topic: str) -> bool:
    heavy_keywords = {"protein", "folding", "robotics", "rlhf", "reinforcement", "climate", "genomics"}
    lower = topic.lower()
    return not any(word in lower for word in heavy_keywords)


def _build_default_snippet(statement: str) -> str:
    return dedent(
        f"""
        import json
        import random
        import statistics

        random.seed(42)
        baseline = [random.gauss(0.68, 0.04) for _ in range(200)]
        variant = [score + random.gauss(0.02, 0.03) for score in baseline]

        baseline_mean = statistics.mean(baseline)
        variant_mean = statistics.mean(variant)
        delta = variant_mean - baseline_mean
        runtime_cost = 0.05

        payload = {{
            "hypothesis": {statement!r},
            "metric_deltas": {{
                "primary_score": round(delta, 6),
                "runtime_cost": runtime_cost
            }},
            "supports": delta >= 0.03 and runtime_cost <= 0.10,
            "confounders": [
                "synthetic_data_only",
                "no_hyperparameter_sweep"
            ]
        }}
        print("RESULT_JSON:" + json.dumps(payload))
        """
    ).strip()
