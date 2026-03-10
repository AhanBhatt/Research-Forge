from agent.nodes.plan_experiment import ExperimentPlanBatch
from schemas.extraction import ResearchObjectExtraction
from schemas.hypothesis import HypothesisBatch
from tools.llm_client import LLMClient


def test_hypothesis_score_normalization_from_rubric_scale() -> None:
    raw = {
        "hypotheses": [
            {
                "hypothesis": "Constrained decoding improves extraction consistency.",
                "novelty": 7,
                "feasibility": 9,
                "information_gain": 8,
                "compute_cost": 3,
            }
        ]
    }
    normalized = LLMClient._normalize_for_schema(raw, HypothesisBatch)
    item = normalized["hypotheses"][0]
    assert item["novelty"] == 0.7
    assert item["feasibility"] == 0.9
    assert item["information_gain"] == 0.8
    assert item["compute_cost"] == 0.3


def test_extraction_alias_normalization() -> None:
    raw = {
        "paper_id": "1234.5678",
        "problem_statement": "Evaluate LLM judge bias",
        "methodology": "Contrastive evaluation over prompt variants",
        "datasets": [{"name": "RewardBench"}],
        "metrics": [{"name": "accuracy"}],
    }
    normalized = LLMClient._normalize_for_schema(raw, ResearchObjectExtraction)
    assert normalized["research_problem"] == "Evaluate LLM judge bias"
    assert normalized["method_summary"] == "Contrastive evaluation over prompt variants"
    assert normalized["datasets"] == ["RewardBench"]
    assert normalized["metrics"] == ["accuracy"]


def test_experiment_plan_missing_fields_filled() -> None:
    raw = {
        "plans": [
            {
                "hypothesis_id": "hyp_1",
                "baseline": "baseline",
                "variant": "variant",
                "metrics": ["accuracy"],
                "executable_locally": False,
            }
        ]
    }
    normalized = LLMClient._normalize_for_schema(raw, ExperimentPlanBatch)
    plan = normalized["plans"][0]
    assert plan["experiment_id"] == "exp_auto_0"
    assert plan["title"] == "Experiment plan 1"
    assert plan["data_requirement"] == "Synthetic or small benchmark slice"
