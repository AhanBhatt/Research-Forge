"""Report writing helpers for markdown and JSON artifacts."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from schemas.run_report import RunReport


class ReportWriter:
    """Persists run artifacts in a timestamped directory."""

    def __init__(self, artifacts_root: Path) -> None:
        self.artifacts_root = artifacts_root

    def write(self, report: RunReport) -> tuple[str, str]:
        run_dir = self.artifacts_root / report.run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        markdown_path = run_dir / "research_report.md"
        json_path = run_dir / "research_report.json"
        markdown_path.write_text(self._build_markdown(report), encoding="utf-8")
        json_path.write_text(json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8")
        return str(markdown_path), str(json_path)

    @staticmethod
    def _build_markdown(report: RunReport) -> str:
        lines: list[str] = []
        lines.append(f"# Research Forge Report: {report.topic}")
        lines.append("")
        lines.append(f"- Run ID: `{report.run_id}`")
        lines.append(f"- Generated: {datetime.utcnow().isoformat()}Z")
        lines.append(f"- Papers Retrieved: {report.summary.papers_retrieved}")
        lines.append(f"- Hypotheses Generated: {report.summary.hypotheses_generated}")
        lines.append(f"- Experiments Executed: {report.summary.experiments_executed}")
        lines.append("")

        lines.append("## Top Papers")
        for paper in report.retrieved_papers[: min(10, len(report.retrieved_papers))]:
            lines.append(f"- **{paper.title}** (`{paper.arxiv_id}`) score={paper.rank_score:.3f}")
        lines.append("")

        lines.append("## Hypotheses")
        for hyp in report.hypotheses:
            lines.append(
                f"- `{hyp.hypothesis_id}`: {hyp.statement} "
                f"(priority={hyp.priority_score:.2f}, novelty={hyp.novelty:.2f}, feasibility={hyp.feasibility:.2f})"
            )
        lines.append("")

        lines.append("## Experiment Outcomes")
        for result in report.experiment_results:
            deltas = ", ".join(f"{k}:{v:+.4f}" for k, v in result.metric_deltas.items()) or "no deltas"
            lines.append(
                f"- `{result.experiment_id}` status={result.status}, outcome={result.hypothesis_outcome}, "
                f"evidence={result.evidence_quality:.2f}, deltas={deltas}"
            )
        lines.append("")

        lines.append("## Reflection")
        for note in report.reflection_notes:
            lines.append(f"- {note}")
        lines.append("")

        lines.append("## Strategy Updates")
        for update in report.strategy_updates:
            lines.append(
                f"- `{update.category}`: predicted={update.predicted}; observed={update.observed}; "
                f"recommendation={update.recommendation}"
            )
        lines.append("")

        lines.append("## Next Research Ideas")
        for idea in report.next_research_ideas:
            lines.append(f"- {idea}")
        lines.append("")
        return "\n".join(lines)
