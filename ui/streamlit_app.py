"""Streamlit demo for the Research Forge MVP."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
from typing import Iterable

import pandas as pd
import streamlit as st

# Ensure project root is importable when Streamlit executes from the `ui/` script path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent import ResearchForgeAgent
from schemas.run_report import ResearchConstraints, ResearchRequest, RunReport

st.set_page_config(page_title="Research Forge", layout="wide")
st.title("Research Forge")
st.caption(
    "Universal self-improving research agent: discover papers, extract structured knowledge, "
    "generate hypotheses, run lightweight experiments, and update strategy memory."
)


def _escape_graphviz_label(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _short(text: str, limit: int = 90) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else compact[: limit - 3] + "..."


def _fmt_score(value: float) -> str:
    return f"{value:.2f}"


def _iter_limit(items: Iterable, limit: int):
    for idx, item in enumerate(items):
        if idx >= limit:
            break
        yield item


def _build_key_graph(report: RunReport, max_papers: int = 6, max_hypotheses: int = 6, max_experiments: int = 6) -> str:
    lines: list[str] = [
        "digraph G {",
        "rankdir=LR;",
        "graph [fontname=Helvetica, fontsize=10, labelloc=t, bgcolor=white];",
        "node [fontname=Helvetica, fontsize=10];",
        "edge [fontname=Helvetica, fontsize=9, color=\"#555555\"];",
    ]

    topic_label = _escape_graphviz_label(report.topic)
    lines.append(f'topic [shape=box,style="rounded,filled",fillcolor="#e8f0ff",label="{topic_label}"];')

    paper_index: dict[str, str] = {}
    hypothesis_index: dict[str, str] = {}
    experiment_index: dict[str, str] = {}
    result_index: dict[str, str] = {}

    paper_subset = list(_iter_limit(report.retrieved_papers, max_papers))
    hypothesis_subset = list(_iter_limit(report.hypotheses, max_hypotheses))
    experiment_subset = list(_iter_limit(report.experiment_plans, max_experiments))
    results_by_experiment = {r.experiment_id: r for r in report.experiment_results}

    for idx, paper in enumerate(paper_subset):
        node_id = f"paper_{idx}"
        paper_index[paper.arxiv_id] = node_id
        label = _escape_graphviz_label(f"{paper.arxiv_id}\\nrank={_fmt_score(paper.rank_score)}")
        lines.append(f'{node_id} [shape=note,style="filled",fillcolor="#f7f7f7",label="{label}"];')
        lines.append(
            f'{node_id} -> topic [label="ABOUT_TOPIC | rank={_fmt_score(paper.rank_score)}", color="#7a7a7a"];'
        )

    for idx, hyp in enumerate(hypothesis_subset):
        node_id = f"hyp_{idx}"
        hypothesis_index[hyp.hypothesis_id] = node_id
        label = _escape_graphviz_label(
            (
                f"{hyp.hypothesis_id}\\n"
                f"priority={_fmt_score(hyp.priority_score)} "
                f"nov={_fmt_score(hyp.novelty)} "
                f"feas={_fmt_score(hyp.feasibility)} "
                f"ig={_fmt_score(hyp.information_gain)} "
                f"cost={_fmt_score(hyp.compute_cost)}"
            )
        )
        lines.append(f'{node_id} [shape=ellipse,style="filled",fillcolor="#fff7db",label="{label}"];')
        lines.append(f'{node_id} -> topic [label="ABOUT_TOPIC", color="#9c8b3f"];')
        for paper_id in hyp.grounding_papers:
            if paper_id in paper_index:
                lines.append(f'{node_id} -> {paper_index[paper_id]} [label="INSPIRED_BY", color="#8f6cc2"];')

    for idx, plan in enumerate(experiment_subset):
        node_id = f"exp_{idx}"
        experiment_index[plan.experiment_id] = node_id
        exec_flag = "exec" if plan.executable_locally and not plan.theoretical_only else "theory"
        label = _escape_graphviz_label(
            f"{plan.experiment_id}\\n{exec_flag} | {plan.estimated_complexity} | {plan.estimated_minutes}m"
        )
        fill = "#e8ffe8" if exec_flag == "exec" else "#f2f2f2"
        lines.append(f'{node_id} [shape=diamond,style="filled",fillcolor="{fill}",label="{label}"];')
        hyp_node = hypothesis_index.get(plan.hypothesis_id)
        if hyp_node:
            lines.append(f'{node_id} -> {hyp_node} [label="TESTS", color="#208090"];')
        else:
            lines.append(f'{node_id} -> topic [label="ABOUT_TOPIC", color="#208090"];')

        result = results_by_experiment.get(plan.experiment_id)
        if not result:
            continue

        result_node = f"res_{idx}"
        result_index[result.experiment_id] = result_node
        primary = result.metric_deltas.get("primary_score", 0.0)
        outcome = result.hypothesis_outcome
        status = result.status
        if outcome == "supported":
            edge_color = "#2f9e44"
            fill_color = "#e6f8ec"
        elif outcome == "unsupported":
            edge_color = "#c92a2a"
            fill_color = "#ffe9e9"
        elif outcome == "inconclusive":
            edge_color = "#e67700"
            fill_color = "#fff3dd"
        else:
            edge_color = "#666666"
            fill_color = "#f5f5f5"

        result_label = _escape_graphviz_label(
            (
                f"{result.experiment_id}_result\\n"
                f"status={status} outcome={outcome}\\n"
                f"delta={primary:+.3f} evidence={_fmt_score(result.evidence_quality)}"
            )
        )
        lines.append(f'{result_node} [shape=box,style="filled",fillcolor="{fill_color}",label="{result_label}"];')
        lines.append(
            (
                f'{node_id} -> {result_node} [label="PRODUCED | status={status} | outcome={outcome}", '
                f'color="{edge_color}", penwidth=2];'
            )
        )

        for conf_idx, confounder in enumerate(_iter_limit(result.confounders, 2)):
            conf_node = f"fm_{idx}_{conf_idx}"
            conf_label = _escape_graphviz_label(_short(confounder, 50))
            lines.append(f'{conf_node} [shape=hexagon,style="filled",fillcolor="#ffe8cc",label="{conf_label}"];')
            lines.append(f'{result_node} -> {conf_node} [label="REVEALS", color="#b35c1e"];')

    lines.append("}")
    return "\n".join(lines)

with st.sidebar:
    st.header("Run Configuration")
    topic = st.text_input("Research Topic", value="LLM evaluation")
    max_papers = st.slider("Max Papers", min_value=3, max_value=40, value=12)
    experiment_budget = st.slider("Experiment Budget", min_value=0, max_value=10, value=2)
    experiments_enabled = st.toggle("Enable Experiments", value=True)
    categories = st.text_input("Preferred arXiv Categories (comma separated)", value="cs.CL,cs.LG")
    date_from = st.date_input("Date From", value=date(2023, 1, 1))
    date_to = st.date_input("Date To", value=date.today())
    run_clicked = st.button("Launch Agent", type="primary")

if run_clicked:
    constraints = ResearchConstraints(
        max_papers=max_papers,
        experiment_budget=experiment_budget,
        experiments_enabled=experiments_enabled,
        preferred_categories=[c.strip() for c in categories.split(",") if c.strip()],
        date_from=date_from,
        date_to=date_to,
    )
    request = ResearchRequest(topic=topic, constraints=constraints)
    with st.spinner("Running Research Forge workflow..."):
        agent = ResearchForgeAgent()
        try:
            report = agent.run(request)
        finally:
            agent.close()
    st.session_state["report"] = report.model_dump(mode="json")

if "report" in st.session_state:
    report = RunReport.model_validate(st.session_state["report"])
    st.success(f"Run completed: {report.run_id}")

    col1, col2, col3 = st.columns(3)
    col1.metric("Papers", report.summary.papers_ranked)
    col2.metric("Hypotheses", report.summary.hypotheses_generated)
    col3.metric("Executed Experiments", report.summary.experiments_executed)

    st.subheader("Retrieved Papers")
    paper_rows = [
        {
            "arxiv_id": p.arxiv_id,
            "title": p.title,
            "rank_score": p.rank_score,
            "categories": ", ".join(p.categories),
        }
        for p in report.retrieved_papers
    ]
    st.dataframe(pd.DataFrame(paper_rows), use_container_width=True)

    st.subheader("Generated Hypotheses")
    hyp_rows = [
        {
            "id": h.hypothesis_id,
            "statement": h.statement,
            "priority": h.priority_score,
            "novelty": h.novelty,
            "feasibility": h.feasibility,
            "info_gain": h.information_gain,
            "compute_cost": h.compute_cost,
        }
        for h in report.hypotheses
    ]
    st.dataframe(pd.DataFrame(hyp_rows), use_container_width=True)

    st.subheader("Experiment Plans")
    plan_rows = [
        {
            "experiment_id": p.experiment_id,
            "hypothesis_id": p.hypothesis_id,
            "complexity": p.estimated_complexity,
            "executable": p.executable_locally,
            "theoretical_only": p.theoretical_only,
            "success_condition": p.success_condition,
        }
        for p in report.experiment_plans
    ]
    st.dataframe(pd.DataFrame(plan_rows), use_container_width=True)

    st.subheader("Results")
    result_rows = [
        {
            "experiment_id": r.experiment_id,
            "status": r.status,
            "outcome": r.hypothesis_outcome,
            "metric_deltas": r.metric_deltas,
            "evidence_quality": r.evidence_quality,
            "next_step": r.likely_next_step,
        }
        for r in report.experiment_results
    ]
    st.dataframe(pd.DataFrame(result_rows), use_container_width=True)

    st.subheader("Reflection / Strategy Updates")
    for update in report.strategy_updates:
        st.markdown(
            f"- **{update.category}** | predicted: `{update.predicted}` | observed: `{update.observed}`\n"
            f"  recommendation: {update.recommendation}"
        )

    st.subheader("Key Graph View")
    c1, c2, c3 = st.columns(3)
    max_graph_papers = c1.slider("Graph papers", min_value=3, max_value=12, value=6, key="graph_papers")
    max_graph_hypotheses = c2.slider("Graph hypotheses", min_value=3, max_value=12, value=6, key="graph_hypotheses")
    max_graph_experiments = c3.slider("Graph experiments", min_value=2, max_value=12, value=6, key="graph_experiments")
    st.caption(
        "Edge labels use Neo4j relationship names: ABOUT_TOPIC, INSPIRED_BY, TESTS, PRODUCED, REVEALS. "
        "PRODUCED edges include status/outcome, and nodes include key scores."
    )
    st.graphviz_chart(
        _build_key_graph(
            report,
            max_papers=max_graph_papers,
            max_hypotheses=max_graph_hypotheses,
            max_experiments=max_graph_experiments,
        )
    )

    st.subheader("Artifacts")
    st.code(f"Markdown: {report.report_markdown_path}\nJSON: {report.report_json_path}")
