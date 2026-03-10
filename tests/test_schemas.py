from datetime import datetime

from pydantic import ValidationError

from schemas.extraction import ResearchObjectExtraction
from schemas.hypothesis import Hypothesis
from schemas.run_report import ResearchConstraints


def test_constraints_validation() -> None:
    constraints = ResearchConstraints(max_papers=10, experiment_budget=3, experiments_enabled=True)
    assert constraints.max_papers == 10
    assert constraints.experiment_budget == 3


def test_constraints_invalid_max_papers() -> None:
    try:
        ResearchConstraints(max_papers=0)
    except ValidationError:
        return
    raise AssertionError("Expected validation error for max_papers=0")


def test_extraction_confidence_bounds() -> None:
    extraction = ResearchObjectExtraction(
        research_problem="Problem",
        main_claims=["Claim"],
        method_summary="Method",
        confidence_score=0.7,
    )
    assert extraction.confidence_score == 0.7


def test_hypothesis_defaults() -> None:
    hyp = Hypothesis(hypothesis_id="h1", statement="X improves Y", rationale="Because", grounding_papers=[])
    assert hyp.priority_score == 0.5
    assert isinstance(datetime.utcnow(), datetime)
