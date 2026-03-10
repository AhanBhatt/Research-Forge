"""Node: convert papers into structured machine-usable objects."""

from __future__ import annotations

import re

from agent.prompts import EXTRACTION_SYSTEM_PROMPT, extraction_user_prompt
from agent.state import ensure_state
from agent.nodes.common import NodeServices
from schemas.extraction import ResearchObjectExtraction
from schemas.paper import Paper


def run(raw_state: dict, services: NodeServices) -> dict:
    state = ensure_state(raw_state)
    extractions: dict[str, dict] = {}
    total_confidence = 0.0

    for paper in state.ranked_papers:
        fallback = lambda p=paper: _heuristic_extraction(p)
        try:
            extraction = services.llm.generate_structured(
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
                user_prompt=extraction_user_prompt(paper),
                schema=ResearchObjectExtraction,
                retries=services.settings.max_extraction_retries,
                fallback_factory=fallback,
            )
        except Exception:
            extraction = fallback()

        extractions[paper.arxiv_id] = extraction.model_dump(mode="json")
        total_confidence += extraction.confidence_score

    avg_confidence = total_confidence / max(1, len(state.ranked_papers))
    logs = state.logs + [
        f"Extracted structured objects for {len(state.ranked_papers)} papers.",
        f"Average extraction confidence={avg_confidence:.2f}.",
    ]
    return {"extractions": extractions, "logs": logs}


def _heuristic_extraction(paper: Paper) -> ResearchObjectExtraction:
    abstract = paper.abstract.strip()
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", abstract) if s.strip()]
    claims = sentences[:2] if sentences else ["Claim not explicitly identified from abstract."]
    limitation_candidates = [
        s for s in sentences if any(k in s.lower() for k in ("limit", "future", "challenge", "however"))
    ]
    metric_candidates = [
        token.strip(".,;:()")
        for token in abstract.split()
        if token.lower().strip(".,;:()")
        in {"accuracy", "f1", "auc", "mse", "rmse", "bleu", "rouge", "map", "ndcg", "latency", "throughput"}
    ]
    dataset_candidates = [
        token.strip(".,;:()")
        for token in abstract.split()
        if token.istitle() and len(token) > 3
    ][:4]

    return ResearchObjectExtraction(
        research_problem=sentences[0] if sentences else paper.title,
        main_claims=claims,
        method_summary=sentences[1] if len(sentences) > 1 else "Method inferred from abstract summary.",
        assumptions=["Assumes abstract faithfully represents method details."],
        datasets=list(dict.fromkeys(dataset_candidates)),
        metrics=list(dict.fromkeys(metric_candidates)) or ["task-specific metric"],
        limitations=limitation_candidates[:3] or ["Limited detail available from abstract-only extraction."],
        future_work=[
            "Validate claims on additional datasets.",
            "Perform ablations to isolate key causal factors.",
        ],
        reproducibility_clues=[
            "Check paper for code repository link.",
            "Extract preprocessing and hyperparameter details from full text.",
        ],
        follow_up_hypotheses=[
            "A constrained variant of the method may reduce variance across datasets.",
            "The method likely performs better under stricter data quality controls.",
        ],
        confidence_score=0.45,
    )
