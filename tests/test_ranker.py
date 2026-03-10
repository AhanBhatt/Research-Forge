from datetime import datetime, timedelta, timezone

from schemas.paper import Paper
from tools.ranker import PaperRanker


def test_ranker_prefers_relevant_paper() -> None:
    now = datetime.now(timezone.utc)
    papers = [
        Paper(
            arxiv_id="1",
            title="Graph neural networks for anomaly detection",
            abstract="Method improves anomaly detection in dynamic graphs.",
            authors=["A"],
            categories=["cs.LG"],
            updated=now,
        ),
        Paper(
            arxiv_id="2",
            title="Quantum optics overview",
            abstract="A survey on optics experiments.",
            authors=["B"],
            categories=["physics.optics"],
            updated=now - timedelta(days=2),
        ),
    ]
    ranked = PaperRanker().rank(papers, "anomaly detection", top_k=2)
    assert ranked[0].arxiv_id == "1"


def test_ranker_recency_decay() -> None:
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=3650)
    papers = [
        Paper(arxiv_id="new", title="A", abstract="A", authors=[], categories=[], updated=now),
        Paper(arxiv_id="old", title="A", abstract="A", authors=[], categories=[], updated=old),
    ]
    ranked = PaperRanker(relevance_weight=0.0, recency_weight=1.0).rank(papers, "A", top_k=2)
    assert ranked[0].arxiv_id == "new"
