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
