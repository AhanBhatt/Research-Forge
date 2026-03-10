"""Node: generate testable hypotheses from structured evidence."""

from __future__ import annotations

import json
from uuid import uuid4

from agent.prompts import HYPOTHESIS_SYSTEM_PROMPT, hypotheses_user_prompt
from agent.state import ensure_state
from agent.nodes.common import NodeServices
from schemas.hypothesis import Hypothesis, HypothesisBatch


def run(raw_state: dict, services: NodeServices) -> dict:
    state = ensure_state(raw_state)
    snapshot_hints = state.strategy_snapshot.hints if state.strategy_snapshot else []
    fallback = lambda: HypothesisBatch(hypotheses=_heuristic_hypotheses(state, services))

    # Avoid costly LLM calls when no evidence was extracted this cycle.
    if not state.extractions:
        heuristics_only = _heuristic_hypotheses(state, services)
        logs = state.logs + [
            "No paper extractions available; skipped LLM hypothesis generation and used heuristic fallback only.",
            f"Generated {len(heuristics_only)} hypotheses.",
        ]
        return {"hypotheses": [h.model_dump(mode="json") for h in heuristics_only], "logs": logs}

    extraction_payload = json.dumps(
        {
            pid: {
                "research_problem": ext.research_problem,
                "main_claims": ext.main_claims[:2],
                "limitations": ext.limitations[:2],
                "datasets": ext.datasets[:2],
                "metrics": ext.metrics[:2],
            }
            for pid, ext in state.extractions.items()
        },
        indent=2,
    )

    try:
        batch = services.llm.generate_structured(
            system_prompt=HYPOTHESIS_SYSTEM_PROMPT,
            user_prompt=hypotheses_user_prompt(state.request.topic, extraction_payload, snapshot_hints),
            schema=HypothesisBatch,
            retries=1,
            fallback_factory=fallback,
        )
    except Exception:
        batch = fallback()

    hypotheses = _normalize_hypotheses(batch.hypotheses, state.request.topic)
    logs = state.logs + [f"Generated {len(hypotheses)} hypotheses."]
    return {"hypotheses": [h.model_dump(mode="json") for h in hypotheses], "logs": logs}


def _normalize_hypotheses(hypotheses: list[Hypothesis], topic: str) -> list[Hypothesis]:
    output: list[Hypothesis] = []
    for hypothesis in hypotheses:
        hyp = hypothesis.model_copy()
        if not hyp.hypothesis_id:
            hyp.hypothesis_id = f"hyp_{uuid4().hex[:8]}"
        if not hyp.statement:
            hyp.statement = f"Controlled change in methods should improve outcomes in {topic}."
        output.append(hyp)
    deduped: dict[str, Hypothesis] = {}
    for hyp in output:
        key = hyp.statement.lower().strip()
        if key not in deduped:
            deduped[key] = hyp
    return list(deduped.values())[:8]


def _heuristic_hypotheses(state, services: NodeServices) -> list[Hypothesis]:
    hypotheses: list[Hypothesis] = []
    topic = state.request.topic
    prior_outcomes = services.memory_retrieval.previous_hypothesis_outcomes(topic, limit=6)
    transfer_concept = services.memory_retrieval.related_concepts(topic, limit=3)

    for paper in state.ranked_papers[:4]:
        extraction = state.extractions.get(paper.arxiv_id)
        if not extraction:
            continue
        limitation = extraction.limitations[0] if extraction.limitations else "reported instability"
        metric = extraction.metrics[0] if extraction.metrics else "task score"
        statement = (
            f"Targeting '{limitation}' in methods related to '{paper.title[:70]}' "
            f"will improve {metric} by at least 3% relative to the paper's baseline."
        )
        hypotheses.append(
            Hypothesis(
                hypothesis_id=f"hyp_{uuid4().hex[:8]}",
                statement=statement,
                rationale=(
                    "Grounded in explicit limitations and empirical metrics extracted from the paper."
                ),
                grounding_papers=[paper.arxiv_id],
                novelty=0.62,
                feasibility=0.68,
                information_gain=0.71,
                compute_cost=0.45,
                expected_direction="improve",
                priority_score=0.64,
            )
        )

    if len(state.ranked_papers) >= 2:
        a, b = state.ranked_papers[0], state.ranked_papers[1]
        concept = transfer_concept[0] if transfer_concept else "regularization"
        hypotheses.append(
            Hypothesis(
                hypothesis_id=f"hyp_{uuid4().hex[:8]}",
                statement=(
                    f"Transferring '{concept}' design choices from {a.arxiv_id} to {b.arxiv_id} "
                    "will increase robustness under distribution shift without increasing compute cost by more than 10%."
                ),
                rationale="Method transfer between adjacent approaches is a high-signal gap strategy.",
                grounding_papers=[a.arxiv_id, b.arxiv_id],
                novelty=0.72,
                feasibility=0.56,
                information_gain=0.76,
                compute_cost=0.52,
                expected_direction="mixed",
                priority_score=0.65,
            )
        )

    if prior_outcomes:
        failed = [o for o in prior_outcomes if o.get("outcome") == "unsupported"]
        if failed:
            hypotheses.append(
                Hypothesis(
                    hypothesis_id=f"hyp_{uuid4().hex[:8]}",
                    statement=(
                        "Replacing high-variance tuning procedures with constrained search will produce "
                        "more reliable gains than prior unsupported variants on the same topic."
                    ),
                    rationale="Derived from prior unsupported outcomes in long-term memory.",
                    grounding_papers=[],
                    novelty=0.58,
                    feasibility=0.79,
                    information_gain=0.69,
                    compute_cost=0.30,
                    expected_direction="improve",
                    priority_score=0.67,
                )
            )
    return hypotheses
