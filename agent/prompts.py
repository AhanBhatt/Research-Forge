"""Prompt templates for LLM-backed nodes."""

from __future__ import annotations

from textwrap import dedent

from schemas.paper import Paper

EXTRACTION_SYSTEM_PROMPT = dedent(
    """
    You are a research extraction engine.
    Extract machine-usable structured objects from scientific papers.
    Avoid generic summaries. Focus on testable claims, methods, assumptions, and reproducibility.
    Return valid JSON only, matching the required schema.
    """
).strip()

HYPOTHESIS_SYSTEM_PROMPT = dedent(
    """
    You are a rigorous research ideation model.
    Generate specific, falsifiable, and feasible hypotheses grounded in provided papers.
    Prioritize contradictions, limitations, and method transfer opportunities.
    Return strict JSON only.
    """
).strip()

EXPERIMENT_PLAN_SYSTEM_PROMPT = dedent(
    """
    You are an experiment planning assistant.
    For each hypothesis, design a compact baseline-vs-variant plan.
    Mark whether local execution is possible in a lightweight Python sandbox.
    Return strict JSON only.
    """
).strip()

RESULT_EVAL_SYSTEM_PROMPT = dedent(
    """
    You evaluate experimental evidence.
    Judge support level, evidence quality, confounders, and next steps conservatively.
    Return strict JSON only.
    """
).strip()


def extraction_user_prompt(paper: Paper) -> str:
    return dedent(
        f"""
        Extract structured research objects from this paper.
        arXiv ID: {paper.arxiv_id}
        Title: {paper.title}
        Abstract: {paper.abstract}
        Authors: {", ".join(paper.authors)}
        Categories: {", ".join(paper.categories)}
        """
    ).strip()


def hypotheses_user_prompt(topic: str, extraction_payload: str, strategy_hints: list[str]) -> str:
    hints_block = "\n".join(f"- {hint}" for hint in strategy_hints) if strategy_hints else "- None"
    return dedent(
        f"""
        Topic: {topic}

        Structured extractions:
        {extraction_payload}

        Prior strategy hints:
        {hints_block}

        Generate 5-8 hypotheses with scores for novelty, feasibility, information_gain, and compute_cost.
        """
    ).strip()


def experiment_plan_user_prompt(topic: str, hypothesis_payload: str, budget: int) -> str:
    return dedent(
        f"""
        Topic: {topic}
        Experiment budget (max runnable plans): {budget}
        Hypotheses:
        {hypothesis_payload}

        Return compact experiment plans. Include python_snippet only when executable_locally is true.
        """
    ).strip()
