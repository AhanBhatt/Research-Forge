from agent.nodes.plan_experiment import _heuristic_plans, _normalize_plan_batch
from schemas.experiment import ExperimentPlan
from schemas.hypothesis import Hypothesis
from tools.python_runner import PythonSandboxRunner


def _sample_hypothesis() -> Hypothesis:
    return Hypothesis(
        hypothesis_id="hyp_1",
        statement="Structured constraints improve evaluation consistency.",
        rationale="Grounded in extraction noise analysis.",
        grounding_papers=["2401.00001"],
    )


def test_normalize_auto_proxy_for_lightweight_topic() -> None:
    hypothesis = _sample_hypothesis()
    plans = [
        ExperimentPlan(
            experiment_id="exp_1",
            hypothesis_id="hyp_1",
            title="Theoretical plan from LLM",
            baseline="Paper baseline",
            variant="Paper variant",
            data_requirement="External benchmark pipeline",
            metrics=["f1"],
            success_condition="N/A",
            estimated_complexity="high",
            executable_locally=False,
            theoretical_only=True,
            python_snippet=None,
            estimated_minutes=60,
        )
    ]

    normalized, auto_proxy_count = _normalize_plan_batch(
        plans,
        experiments_enabled=True,
        topic="LLM evaluation",
        hypotheses=[hypothesis],
    )

    plan = normalized[0]
    assert auto_proxy_count == 1
    assert plan.executable_locally
    assert not plan.theoretical_only
    assert plan.python_snippet is not None
    assert "RESULT_JSON:" in plan.python_snippet
    assert "primary_score" in plan.metrics

    runner = PythonSandboxRunner(timeout_seconds=5)
    assert runner._check_safety(plan.python_snippet) is None


def test_normalize_keeps_heavy_topic_theoretical() -> None:
    hypothesis = _sample_hypothesis()
    plans = [
        ExperimentPlan(
            experiment_id="exp_2",
            hypothesis_id="hyp_1",
            title="Theoretical plan from LLM",
            baseline="Paper baseline",
            variant="Paper variant",
            data_requirement="Molecular simulation cluster",
            metrics=["f1"],
            success_condition="N/A",
            estimated_complexity="high",
            executable_locally=False,
            theoretical_only=True,
            python_snippet=None,
            estimated_minutes=120,
        )
    ]

    normalized, auto_proxy_count = _normalize_plan_batch(
        plans,
        experiments_enabled=True,
        topic="protein folding",
        hypotheses=[hypothesis],
    )

    plan = normalized[0]
    assert auto_proxy_count == 0
    assert not plan.executable_locally
    assert plan.theoretical_only
    assert plan.python_snippet is None


def test_heuristic_plans_build_runnable_snippets_for_light_topics() -> None:
    plans = _heuristic_plans([_sample_hypothesis()], "anomaly detection", True)
    plan = plans[0]

    assert plan.executable_locally
    assert not plan.theoretical_only
    assert plan.python_snippet is not None
    assert "f1_variant" in plan.python_snippet
    assert "primary_score" in plan.metrics
