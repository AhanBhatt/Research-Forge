"""Node: create executable or theoretical experiment plans."""

from __future__ import annotations

import json
from textwrap import dedent
from typing import Any
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
        plans, auto_proxy_count = _normalize_plan_batch(
            batch.plans,
            constraints.experiments_enabled,
            state.request.topic,
            candidates,
        )
    except Exception:
        plans = _heuristic_plans(candidates, state.request.topic, constraints.experiments_enabled)
        auto_proxy_count = sum(1 for plan in plans if plan.executable_locally and not plan.theoretical_only and bool(plan.python_snippet))

    if services.neo4j.enabled:
        for plan in plans:
            services.neo4j.upsert_experiment(plan.model_dump(mode="json"))

    logs = state.logs + [
        (
            f"Planned {len(plans)} experiments ({'enabled' if constraints.experiments_enabled else 'disabled'}), "
            f"auto-proxy runnable={auto_proxy_count}."
        )
    ]
    return {"experiment_plans": [plan.model_dump(mode="json") for plan in plans], "logs": logs}


def _normalize_plan_batch(
    plans: list[ExperimentPlan],
    experiments_enabled: bool,
    topic: str,
    hypotheses: list[Hypothesis],
) -> tuple[list[ExperimentPlan], int]:
    output: list[ExperimentPlan] = []
    auto_proxy_count = 0
    lightweight_topic = _is_lightweight_topic(topic)
    hypothesis_by_id = {hyp.hypothesis_id: hyp for hyp in hypotheses}

    for plan in plans:
        update = {}
        if not plan.experiment_id:
            update["experiment_id"] = f"exp_{uuid4().hex[:8]}"
        normalized = plan.model_copy(update=update)
        if not experiments_enabled:
            normalized = normalized.model_copy(update={"executable_locally": False, "theoretical_only": True, "python_snippet": None})
        elif lightweight_topic and _needs_proxy_upgrade(normalized):
            statement = _resolve_statement_for_plan(normalized, hypothesis_by_id)
            proxy_spec = _build_proxy_spec(topic, statement)
            normalized = normalized.model_copy(
                update={
                    "data_requirement": proxy_spec["data_requirement"],
                    "metrics": proxy_spec["metrics"],
                    "success_condition": proxy_spec["success_condition"],
                    "estimated_complexity": proxy_spec["estimated_complexity"],
                    "estimated_minutes": proxy_spec["estimated_minutes"],
                    "executable_locally": True,
                    "theoretical_only": False,
                    "python_snippet": proxy_spec["python_snippet"],
                }
            )
            auto_proxy_count += 1
        elif normalized.executable_locally and normalized.python_snippet and normalized.theoretical_only:
            normalized = normalized.model_copy(update={"theoretical_only": False})
        output.append(normalized)
    return output, auto_proxy_count


def _heuristic_plans(hypotheses: list[Hypothesis], topic: str, experiments_enabled: bool) -> list[ExperimentPlan]:
    plans: list[ExperimentPlan] = []
    for idx, hypothesis in enumerate(hypotheses, start=1):
        executable = experiments_enabled and _is_lightweight_topic(topic)
        theoretical_only = not executable
        proxy_spec = _build_proxy_spec(topic, hypothesis.statement) if executable else None
        plans.append(
            ExperimentPlan(
                experiment_id=f"exp_{uuid4().hex[:8]}",
                hypothesis_id=hypothesis.hypothesis_id,
                title=f"Baseline-vs-variant test #{idx}",
                baseline="Current best-practice baseline from retrieved papers",
                variant=f"Targeted intervention for hypothesis: {hypothesis.statement}",
                data_requirement=(
                    str(proxy_spec["data_requirement"])
                    if proxy_spec
                    else "Requires external domain datasets and evaluation pipeline."
                ),
                metrics=list(proxy_spec["metrics"]) if proxy_spec else ["primary_score", "runtime_cost"],
                success_condition=(
                    str(proxy_spec["success_condition"])
                    if proxy_spec
                    else "Define domain-specific success criteria before execution."
                ),
                estimated_complexity=str(proxy_spec["estimated_complexity"]) if proxy_spec else "high",
                executable_locally=executable,
                theoretical_only=theoretical_only,
                python_snippet=str(proxy_spec["python_snippet"]) if proxy_spec else None,
                estimated_minutes=int(proxy_spec["estimated_minutes"]) if proxy_spec else 45,
            )
        )
    return plans


def _is_lightweight_topic(topic: str) -> bool:
    heavy_keywords = {
        "protein",
        "folding",
        "robotics",
        "rlhf",
        "reinforcement",
        "genomics",
        "molecular",
        "drug discovery",
        "radiology",
        "materials",
    }
    lower = topic.lower()
    return not any(word in lower for word in heavy_keywords)


def _needs_proxy_upgrade(plan: ExperimentPlan) -> bool:
    return (not plan.executable_locally) or plan.theoretical_only or not bool(plan.python_snippet)


def _resolve_statement_for_plan(plan: ExperimentPlan, hypothesis_by_id: dict[str, Hypothesis]) -> str:
    source = hypothesis_by_id.get(plan.hypothesis_id)
    if source:
        return source.statement
    if plan.variant.strip():
        return plan.variant
    return plan.title


def _build_proxy_spec(topic: str, statement: str) -> dict[str, Any]:
    family = _topic_family(topic)
    if family == "time_series":
        return {
            "data_requirement": "Synthetic autoregressive time-series sequence generated in-script.",
            "metrics": ["primary_score", "runtime_cost", "mae_baseline", "mae_variant"],
            "success_condition": "MAE improvement >= 0.015 with runtime_cost <= 0.10.",
            "estimated_complexity": "low",
            "estimated_minutes": 8,
            "python_snippet": _build_time_series_proxy_snippet(statement),
        }
    if family == "anomaly":
        return {
            "data_requirement": "Synthetic mixture with injected anomalies generated in-script.",
            "metrics": ["primary_score", "runtime_cost", "f1_baseline", "f1_variant"],
            "success_condition": "F1 improvement >= 0.020 with runtime_cost <= 0.12.",
            "estimated_complexity": "low",
            "estimated_minutes": 8,
            "python_snippet": _build_anomaly_proxy_snippet(statement),
        }
    if family == "graph":
        return {
            "data_requirement": "Synthetic node-level graph statistics generated in-script.",
            "metrics": ["primary_score", "runtime_cost", "accuracy_baseline", "accuracy_variant"],
            "success_condition": "Accuracy improvement >= 0.020 with runtime_cost <= 0.10.",
            "estimated_complexity": "low",
            "estimated_minutes": 7,
            "python_snippet": _build_graph_proxy_snippet(statement),
        }
    if family == "llm_eval":
        return {
            "data_requirement": "Synthetic pairwise preference dataset generated in-script.",
            "metrics": ["primary_score", "runtime_cost", "accuracy_baseline", "accuracy_variant"],
            "success_condition": "Pairwise accuracy improvement >= 0.020 with runtime_cost <= 0.12.",
            "estimated_complexity": "low",
            "estimated_minutes": 7,
            "python_snippet": _build_llm_eval_proxy_snippet(statement),
        }
    return {
        "data_requirement": "Synthetic baseline-vs-variant simulation generated in-script.",
        "metrics": ["primary_score", "runtime_cost", "baseline_score", "variant_score"],
        "success_condition": "primary_score improvement >= 0.030 with runtime_cost <= 0.10.",
        "estimated_complexity": "low",
        "estimated_minutes": 8,
        "python_snippet": _build_default_proxy_snippet(statement),
    }


def _topic_family(topic: str) -> str:
    lower = topic.lower()
    if any(token in lower for token in ("time series", "forecast", "forecasting")):
        return "time_series"
    if any(token in lower for token in ("anomaly", "outlier", "fraud", "intrusion")):
        return "anomaly"
    if any(token in lower for token in ("graph", "gnn", "network")):
        return "graph"
    if any(token in lower for token in ("llm", "language model", "evaluation", "nlp", "prompt")):
        return "llm_eval"
    return "generic"


def _build_default_proxy_snippet(statement: str) -> str:
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
                "runtime_cost": runtime_cost,
                "baseline_score": round(baseline_mean, 6),
                "variant_score": round(variant_mean, 6),
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


def _build_time_series_proxy_snippet(statement: str) -> str:
    return dedent(
        f"""
        import json
        import random
        import statistics

        random.seed(17)
        series = [0.0]
        for _ in range(240):
            nxt = 0.78 * series[-1] + random.gauss(0.0, 0.4)
            series.append(nxt)
        series = series[1:]

        split = 180
        train = series[:split]
        test = series[split:]

        baseline_pred = []
        last = train[-1]
        for actual in test:
            baseline_pred.append(last)
            last = actual

        variant_pred = []
        history = train[-3:]
        for actual in test:
            pred = sum(history[-3:]) / 3.0
            variant_pred.append(pred)
            history.append(actual)

        mae_baseline = statistics.mean(abs(y - yhat) for y, yhat in zip(test, baseline_pred))
        mae_variant = statistics.mean(abs(y - yhat) for y, yhat in zip(test, variant_pred))
        delta = mae_baseline - mae_variant
        runtime_cost = 0.06

        payload = {{
            "hypothesis": {statement!r},
            "metric_deltas": {{
                "primary_score": round(delta, 6),
                "runtime_cost": runtime_cost,
                "mae_baseline": round(mae_baseline, 6),
                "mae_variant": round(mae_variant, 6),
            }},
            "supports": delta >= 0.015 and runtime_cost <= 0.10,
            "confounders": [
                "single_synthetic_series",
                "no_seasonality_modeling",
            ]
        }}
        print("RESULT_JSON:" + json.dumps(payload))
        """
    ).strip()


def _build_anomaly_proxy_snippet(statement: str) -> str:
    return dedent(
        f"""
        import json
        import random
        import statistics

        random.seed(23)
        scores = []
        labels = []
        for _ in range(360):
            scores.append(random.gauss(0.0, 1.0))
            labels.append(0)
        for _ in range(40):
            scores.append(random.gauss(3.2, 0.7))
            labels.append(1)

        mean = statistics.mean(scores)
        std = statistics.pstdev(scores) + 1e-9
        median = statistics.median(scores)
        mad = statistics.median(abs(x - median) for x in scores) + 1e-9

        baseline_pred = [1 if s > mean + 3.0 * std else 0 for s in scores]
        variant_pred = [1 if abs(s - median) > 3.0 * 1.4826 * mad else 0 for s in scores]

        def f1(y_true, y_pred):
            tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
            fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
            fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
            precision = tp / (tp + fp + 1e-9)
            recall = tp / (tp + fn + 1e-9)
            return 2 * precision * recall / (precision + recall + 1e-9)

        f1_baseline = f1(labels, baseline_pred)
        f1_variant = f1(labels, variant_pred)
        delta = f1_variant - f1_baseline
        runtime_cost = 0.07

        payload = {{
            "hypothesis": {statement!r},
            "metric_deltas": {{
                "primary_score": round(delta, 6),
                "runtime_cost": runtime_cost,
                "f1_baseline": round(f1_baseline, 6),
                "f1_variant": round(f1_variant, 6),
            }},
            "supports": delta >= 0.02 and runtime_cost <= 0.12,
            "confounders": [
                "simplified_univariate_scores",
                "fixed_thresholds",
            ]
        }}
        print("RESULT_JSON:" + json.dumps(payload))
        """
    ).strip()


def _build_graph_proxy_snippet(statement: str) -> str:
    return dedent(
        f"""
        import json
        import random

        random.seed(31)
        labels = []
        degrees = []
        feature = []
        for _ in range(420):
            label = 1 if random.random() < 0.5 else 0
            labels.append(label)
            degree = random.randint(9, 20) if label == 1 else random.randint(1, 12)
            degrees.append(degree)
            signal = (1.0 if label == 1 else -1.0) + random.gauss(0.0, 0.9)
            feature.append(signal)

        baseline_pred = [1 if x > 0 else 0 for x in feature]
        variant_pred = [1 if (0.12 * d + x) > 1.4 else 0 for d, x in zip(degrees, feature)]

        acc_baseline = sum(1 for y, p in zip(labels, baseline_pred) if y == p) / len(labels)
        acc_variant = sum(1 for y, p in zip(labels, variant_pred) if y == p) / len(labels)
        delta = acc_variant - acc_baseline
        runtime_cost = 0.05

        payload = {{
            "hypothesis": {statement!r},
            "metric_deltas": {{
                "primary_score": round(delta, 6),
                "runtime_cost": runtime_cost,
                "accuracy_baseline": round(acc_baseline, 6),
                "accuracy_variant": round(acc_variant, 6),
            }},
            "supports": delta >= 0.02 and runtime_cost <= 0.10,
            "confounders": [
                "no_real_graph_topology_simulation",
                "single_proxy_task",
            ]
        }}
        print("RESULT_JSON:" + json.dumps(payload))
        """
    ).strip()


def _build_llm_eval_proxy_snippet(statement: str) -> str:
    return dedent(
        f"""
        import json
        import random

        random.seed(13)
        pairs = []
        for _ in range(260):
            qa = random.gauss(0.0, 1.0)
            qb = random.gauss(0.0, 1.0)
            true_label = 1 if qa > qb else 0
            pairs.append((qa, qb, true_label))

        baseline_correct = 0
        variant_correct = 0

        for qa, qb, true_label in pairs:
            base_pred = 1 if (qa + random.gauss(0.0, 0.45)) > (qb + random.gauss(0.0, 0.45)) else 0
            var_pred = 1 if (qa + random.gauss(0.0, 0.25)) > (qb + random.gauss(0.0, 0.25)) else 0
            baseline_correct += 1 if base_pred == true_label else 0
            variant_correct += 1 if var_pred == true_label else 0

        acc_baseline = baseline_correct / len(pairs)
        acc_variant = variant_correct / len(pairs)
        delta = acc_variant - acc_baseline
        runtime_cost = 0.08

        payload = {{
            "hypothesis": {statement!r},
            "metric_deltas": {{
                "primary_score": round(delta, 6),
                "runtime_cost": runtime_cost,
                "accuracy_baseline": round(acc_baseline, 6),
                "accuracy_variant": round(acc_variant, 6),
            }},
            "supports": delta >= 0.02 and runtime_cost <= 0.12,
            "confounders": [
                "simulated_judges_only",
                "no_real_model_outputs",
            ]
        }}
        print("RESULT_JSON:" + json.dumps(payload))
        """
    ).strip()
