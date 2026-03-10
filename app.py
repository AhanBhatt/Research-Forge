"""CLI entry point for Research Forge."""

from __future__ import annotations

import argparse
import logging
from datetime import date

from agent import ResearchForgeAgent
from schemas.run_report import ResearchConstraints, ResearchRequest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Research Forge agent.")
    parser.add_argument("--topic", required=True, help="Research topic, e.g., 'LLM evaluation'")
    parser.add_argument("--max-papers", type=int, default=12, help="Maximum papers to keep after ranking")
    parser.add_argument("--categories", type=str, default="", help="Comma-separated arXiv categories")
    parser.add_argument("--date-from", type=str, default="", help="Start date YYYY-MM-DD")
    parser.add_argument("--date-to", type=str, default="", help="End date YYYY-MM-DD")
    parser.add_argument("--experiment-budget", type=int, default=2, help="Maximum planned experiments")
    parser.add_argument("--no-experiments", action="store_true", help="Disable local experiment execution")
    return parser.parse_args()


def parse_optional_date(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    # Neo4j emits verbose schema notifications on empty/fresh graphs; keep CLI output focused.
    logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)
    logging.getLogger("neo4j.pool").setLevel(logging.ERROR)
    args = parse_args()
    categories = [item.strip() for item in args.categories.split(",") if item.strip()]
    constraints = ResearchConstraints(
        max_papers=args.max_papers,
        preferred_categories=categories,
        date_from=parse_optional_date(args.date_from),
        date_to=parse_optional_date(args.date_to),
        experiment_budget=args.experiment_budget,
        experiments_enabled=not args.no_experiments,
    )
    request = ResearchRequest(topic=args.topic, constraints=constraints)

    agent = ResearchForgeAgent()
    try:
        report = agent.run(request)
    finally:
        agent.close()

    print(f"Run complete: {report.run_id}")
    print(f"Topic: {report.topic}")
    print(
        "Summary: "
        f"papers={report.summary.papers_ranked}, "
        f"hypotheses={report.summary.hypotheses_generated}, "
        f"executed_experiments={report.summary.experiments_executed}"
    )
    print(f"Markdown report: {report.report_markdown_path}")
    print(f"JSON report: {report.report_json_path}")


if __name__ == "__main__":
    main()
