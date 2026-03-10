"""Streamlit demo for the Research Forge MVP."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

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
    graph_lines = ["digraph G {", "rankdir=LR;", f'topic [shape=box,label="{report.topic}"];']
    for idx, paper in enumerate(report.retrieved_papers[:5]):
        node = f"paper_{idx}"
        graph_lines.append(f'{node} [shape=note,label="{paper.arxiv_id}"];')
        graph_lines.append(f"topic -> {node};")
    for idx, hyp in enumerate(report.hypotheses[:5]):
        node = f"hyp_{idx}"
        graph_lines.append(f'{node} [shape=ellipse,label="{hyp.hypothesis_id}"];')
        graph_lines.append(f"topic -> {node};")
    for idx, plan in enumerate(report.experiment_plans[:5]):
        node = f"exp_{idx}"
        graph_lines.append(f'{node} [shape=diamond,label="{plan.experiment_id}"];')
        graph_lines.append(f"topic -> {node};")
    graph_lines.append("}")
    st.graphviz_chart("\n".join(graph_lines))

    st.subheader("Artifacts")
    st.code(f"Markdown: {report.report_markdown_path}\nJSON: {report.report_json_path}")
